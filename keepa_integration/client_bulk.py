import requests
import datetime
import json
import os

from config import KEEPA_API_KEY, AMAZON_DOMAIN_ID
from keepa_integration.client import (
    keepa_time_to_date,
    to_dollars,
    parse_bsr_times,
    sum_all_stocks,
    count_competitive_sellers
)

def count_sellers(product):
    """
    Return a tuple (fba_count, mf_count, total) for the active/live offers of this product.
    We look at product["offers"] + product["liveOffersOrder"] to figure out
    which offers are currently active, then increment counters based on isAmazon/isFBA flags.
    """
    offers = product.get("offers", [])
    live_order = product.get("liveOffersOrder", [])
    fba_count = 0
    mf_count = 0

    for idx in live_order:
        if idx < len(offers):
            off = offers[idx]
            if off.get("isAmazon"):       # Amazon official seller
                fba_count += 1
            elif off.get("isFBA"):       # 3P FBA
                fba_count += 1
            else:                        # MF or "Seller Fulfilled Prime" unknown
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
      - Debug prints to confirm pickAndPackFee

    Returns a list of dicts, each dict representing one Keepa product transformed.
    """

    # 1) Convert UPC list to a comma-separated string
    code_str = ",".join(upc_list)

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

    print(f"[DEBUG] fetch_bulk_product_data() => Requesting from Keepa with UPC(s): {upc_list}")
    print(f"[DEBUG] Keepa request params => {params}")

    # 3) Send the request to Keepa
    base_url = "https://api.keepa.com/product"
    resp = requests.get(base_url, params=params)
    if resp.status_code != 200:
        print(f"[ERROR] Keepa returned HTTP {resp.status_code}")
        return []

    # 4) Parse the JSON, save a raw debug copy
    raw_json = resp.json()
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
        bought_in_past_month = monthly_sold if (isinstance(monthly_sold, int) and monthly_sold > 0) else "N/A"

        # Compute estimated sales => ratio c_bsr / b30
        estimated_sales = "N/A"
        if (isinstance(c_bsr, int) and c_bsr > 0 and
            isinstance(b30, int)   and b30 > 0   and
            isinstance(monthly_sold, int) and monthly_sold > 0):
            ratio = c_bsr / b30
            estimated_sales = int(monthly_sold * ratio)

        # Star rating & rating count from CSV index 16/17
        csv_data = product.get("csv", [])
        def last_val(arr):
            return arr[-1] if (len(arr)>=2 and isinstance(arr[-1], int) and arr[-1]>=0) else None

        star_val   = last_val(csv_data[16]) if len(csv_data)>16 and isinstance(csv_data[16], list) else None
        rating_val = last_val(csv_data[17]) if len(csv_data)>17 and isinstance(csv_data[17], list) else None
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
            doc   = round((total_inven / estimated_sales)*30, 1)
            sales = monthly_sold

        # Seller info
        is_amz = stats.get("buyBoxIsAmazon", False)
        comp   = count_competitive_sellers(product)
        fba_cnt, mf_cnt, tot_cnt = count_sellers(product)

        # 2) fetch FBA fee from product stats => "pickAndPackFee"

        pickAndPackFee_cents = product.get("fbaFees", {}).get("pickAndPackFee", 0)

        fba_fee = pickAndPackFee_cents / 100.0

        # fallback referral fee to 15% if missing
        referral_fee_pct = stats.get("referralFeePercentage", 15.0)

        # Debug printing to confirm the fee
        print(f"[DEBUG] ASIN {asin}: pickAndPackFee_cents={pickAndPackFee_cents} => fba_fee={fba_fee}")

        # Build final record
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
            # FBA/Referral fees for use in front-end calculations
            "fba_fee": fba_fee,
            "referral_fee_pct": referral_fee_pct
        }

        final_data_list.append(final_data)

    
    # raw_json = resp.json()

    # # 4) Save raw response for debugging
    # with open("bulk_upc_results_raw.json", "w", encoding="utf-8") as f:
    #     json.dump(raw_json, f, indent=2)
    # # 6) Save the simplified results for debugging
    # with open("bulk_upc_results.json", "w", encoding="utf-8") as f:
    #     json.dump(final_data_list, f, indent=2)

    return final_data_list
