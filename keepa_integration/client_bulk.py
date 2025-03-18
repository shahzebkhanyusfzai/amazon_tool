# keepa_integration/client_bulk.py

import requests
import datetime
import json
import os
import time

from config import KEEPA_API_KEY, AMAZON_DOMAIN_ID
from keepa_integration.client import (
    keepa_time_to_date,
    to_dollars,
    parse_bsr_times,
    sum_all_stocks,
    count_competitive_sellers
)

# ---------------------------------------------------------------------
# Add these constants for retry logic:
MAX_RETRIES = 5         # how many times we'll retry on 429

def safe_keepa_request(params):
    base_url = "https://api.keepa.com/product"
    attempts = 0

    # attempts 1 => 120s(2m), attempts 2 => 300s(5m), attempts 3 => 600s(10m), ...
    WAIT_MAPPING = {
        1: 120,
        2: 300,
        3: 600,
        4: 900,
        5: 1200,
    }

    code_str = params.get("code", "")
    code_list = code_str.split(",")
    short_str = ", ".join(code_list[:3])

    while attempts < MAX_RETRIES:
        attempts += 1
        print(f"[DEBUG safe_keepa_request] Attempt {attempts}/{MAX_RETRIES} -> first few codes: [{short_str}]")

        resp = requests.get(base_url, params=params)

        if resp.status_code == 429:
            wait_time = WAIT_MAPPING.get(attempts, 1200)  # fallback if attempts>5
            print(f"[WARN] Got 429 from Keepa => sleeping {wait_time} seconds.")
            time.sleep(wait_time)
            continue
        elif resp.status_code != 200:
            print(f"[ERROR] Keepa returned HTTP {resp.status_code} (non-429). No retry for now.")
            return None
        else:
            return resp.json()

    print(f"[ERROR] Gave up after {MAX_RETRIES} attempts for codes: [{short_str}]")
    return None

def count_sellers(product):
    """
    Return a tuple (fba_count, mf_count, total).
    """
    offers = product.get("offers", [])

    # Safely handle possible `null`
    live_order = product.get("liveOffersOrder")
    if not isinstance(live_order, list):
        live_order = []

    fba_count = 0
    mf_count = 0

    for idx in live_order:
        if idx < len(offers):
            off = offers[idx]
            if off.get("isAmazon"):  # ...
                fba_count += 1
            elif off.get("isFBA"):
                fba_count += 1
            else:
                mf_count += 1

    total = fba_count + mf_count
    return (fba_count, mf_count, total)


def fetch_bulk_product_data(upc_list, cost_of_goods=0.0):
    """
    For a list of UPCs, call the Keepa /product?code=... endpoint to fetch product data.
    We'll request stats, buybox, offers, stock, and rating, plus 90 days of history.
    Then we build a simplified array of product results that includes:
      - Basic listing info (ASIN, Title, Brand)
      - Pricing (Current, 30-day, 90-day, Best [Min])
      - Ranking, #Sellers, Inventory stats
      - FBA Fee + referral fee percentage
      - (Empty) profitability field for now
    """
    # 1) Convert UPC list to a comma-separated string
    code_str = ",".join(upc_list)

    # For debug: Show only first 3 codes
    debug_upc_preview = ", ".join(upc_list[:3])
    print(f"[DEBUG fetch_bulk_product_data] => upc_list size={len(upc_list)}; first few => [{debug_upc_preview}]")

    # 2) Build query params for Keepa
    params = {
        "key": KEEPA_API_KEY,
        "domain": AMAZON_DOMAIN_ID,
        "code": code_str,
        "stats": 30,        # stats for last 30 days
        "buybox": 1,        # add buy box data
        "offers": 20,       # up to 20 offers
        "stock": 1,         # get stock info
        "rating": 1,        # rating & review count
        "history": 1,       # include historical data
        "days": 90,         # limit historical to 90 days
        "code-limit": 20    # up to 20 products per code
    }

    print("[DEBUG fetch_bulk_product_data] => sending request to Keepa ...")

    # 3) Use the safe_keepa_request (with 429 handling)
    raw_json = safe_keepa_request(params)
    if raw_json is None:
        print("[ERROR] No response from Keepa (raw_json=None).")
        return []
    # else:   
    #     print("=== DEBUG: Full Keepa response for this chunk ===")
    #     print(json.dumps(raw_json, indent=2))  # or a truncated version


    # 4) Parse the JSON, save a raw debug copy
    with open("bulk_upc_results_raw.json", "w", encoding="utf-8") as f:
        json.dump(raw_json, f, indent=2)

    products = raw_json.get("products", [])
    print(f"[DEBUG] Keepa responded with {len(products)} product(s).")

    if not products:
        print("[WARNING] No products returned from Keepa for these UPCs.")
        return []

    # 5) Build a simplified final list
    final_data_list = []

    for product in products:
        asin  = product.get("asin", "N/A")
        stats = product.get("stats", {})
        brand = product.get("brand", "N/A")
        title = product.get("title", "N/A")

        # BSR Times (c_bsr, 90-day, 30-day, best)
        c_bsr, b90, b30, b_best = parse_bsr_times(product)

        # Monthly Sold
        monthly_sold = product.get("monthlySold", 0)
        if isinstance(monthly_sold, int) and monthly_sold > 0:
            bought_in_past_month = monthly_sold
        else:
            bought_in_past_month = "N/A"

        # Compute estimated sales => ratio c_bsr / b30
        estimated_sales = "N/A"
        if (isinstance(c_bsr, int) and c_bsr > 0 and
            isinstance(b30, int)   and b30 > 0   and
            isinstance(monthly_sold, int) and monthly_sold > 0):
            ratio = c_bsr / b30
            estimated_sales = int(monthly_sold * ratio)

        # CSV => rating
        csv_data = product.get("csv", [])
        def last_val(arr):
            return arr[-1] if (len(arr)>=2 and isinstance(arr[-1], int) and arr[-1]>=0) else None

        star_val   = None
        rating_val = None
        if len(csv_data)>16 and isinstance(csv_data[16], list):
            star_val = last_val(csv_data[16])
        if len(csv_data)>17 and isinstance(csv_data[17], list):
            rating_val = last_val(csv_data[17])

        star_str   = "N/A" if star_val   is None else f"{star_val/10:.1f}"
        rating_str = "N/A" if rating_val is None else str(rating_val)

        # Pricing (Current, 30d, 90d, Best)
        bb_price = stats.get("buyBoxPrice", -1)
        if bb_price < 0:
            c_prices = stats.get("current", [])
            if c_prices and isinstance(c_prices[0], int) and c_prices[0]>=0:
                bb_price = c_prices[0]

        p30 = -1
        if isinstance(stats.get("avg30"), list) and stats["avg30"]:
            p30 = stats["avg30"][0]

        p90 = -1
        if isinstance(stats.get("avg90"), list) and stats["avg90"]:
            p90 = stats["avg90"][0]

        best_price_cents = -1
        mm = stats.get("min", [])
        if mm and isinstance(mm[0], list) and len(mm[0])==2 and isinstance(mm[0][1], int):
            best_price_cents = mm[0][1]

        # Inventory
        total_inven = sum_all_stocks(product)
        if not (isinstance(monthly_sold, int) and monthly_sold>0):
            doc = "N/A"
            sales = "N/A"
        else:
            # days of cover
            if isinstance(estimated_sales, int) and estimated_sales>0:
                doc = round((total_inven / estimated_sales)*30, 1)
            else:
                doc = "N/A"
            sales = monthly_sold

        # Seller info
        is_amz = stats.get("buyBoxIsAmazon", False)
        comp   = count_competitive_sellers(product)
        fba_cnt, mf_cnt, tot_cnt = count_sellers(product)

        # pickAndPackFee
        fba_fees = product.get("fbaFees")
        if not isinstance(fba_fees, dict):
            fba_fees = {}
        pickAndPackFee_cents = fba_fees.get("pickAndPackFee", 0)
        fba_fee = pickAndPackFee_cents / 100.0

        # fallback referral fee to 15% if missing
        referral_fee_pct = stats.get("referralFeePercentage", 15.0)

        print(f"[DEBUG] ASIN {asin} => pickAndPackFee_cents={pickAndPackFee_cents} => fba_fee={fba_fee}")

        final_data = {
            "asin": asin,
            "upc": product.get("upcList", []),
            "title": title,
            "brand": brand,
            "domainId": product.get("domainId"),
            "rating": {
                "star":  star_str,
                "count": rating_str
            },
            "pricing": {
                "current": to_dollars(bb_price),
                "avg90":   to_dollars(p90),
                "avg30":   to_dollars(p30),
                "best":    to_dollars(best_price_cents),
            },
            "ranking": {
                "current": c_bsr,
                "avg90":   b90,
                "avg30":   b30,
                "best":    b_best
            },
            "#sellers": {
                "FBA": fba_cnt,
                "MF": mf_cnt,
                "Competitive": comp,
                "Total": tot_cnt,
                "IsAmazon": is_amz
            },
            "inventory": {
                "totalStock": total_inven,
                "daysOfCover": doc,
                "monthlySold": sales
            },
            "profitability": " ",  # placeholder
            "boughtInPastMonth": bought_in_past_month,
            "estimatedSales": estimated_sales,
            "fba_fee": fba_fee,
            "referral_fee_pct": referral_fee_pct
        }

        final_data_list.append(final_data)

    return final_data_list


def fetch_bulk_product_data_all(all_upcs, cost_of_goods=0.0):
    """
    If more than 100 upcs, chunk them and combine the results 
    from fetch_bulk_product_data (which handles up to 100 at once).
    """
    CHUNK_SIZE = 100
    final_results = []

    if not all_upcs:
        print("[WARNING] fetch_bulk_product_data_all => Received an empty list of UPCs.")
        return []

    total_count = len(all_upcs)
    print(f"[DEBUG] fetch_bulk_product_data_all => total upcs = {total_count}")

    if len(all_upcs) <= CHUNK_SIZE:
        # Single chunk
        print(f"[DEBUG] single-chunk scenario => upcs={len(all_upcs)} => {all_upcs[:3]}")
        return fetch_bulk_product_data(all_upcs, cost_of_goods=cost_of_goods)

    # otherwise chunk it up
    chunk_number = 0
    for i in range(0, len(all_upcs), CHUNK_SIZE):
        chunk_number += 1
        chunk = all_upcs[i : i+CHUNK_SIZE]
        short_preview = ", ".join(chunk[:3])
        print(f"\n[DEBUG] CHUNK #{chunk_number} => size={len(chunk)} => first few = [{short_preview}]")

        chunk_results = fetch_bulk_product_data(chunk, cost_of_goods=cost_of_goods)
        print(f"[DEBUG] chunk #{chunk_number} => got {len(chunk_results)} products back from Keepa")

        final_results.extend(chunk_results)

    print(f"[DEBUG] All chunks done => total final_results size = {len(final_results)}")

    return final_results
