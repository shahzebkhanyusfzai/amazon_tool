import requests
from config import KEEPA_API_KEY, AMAZON_DOMAIN_ID
import datetime

def keepa_time_to_date(keepa_ts):
    """Convert Keepa's minute timestamp into 'YYYY-MM-DD' string."""
    base_date = datetime.datetime(2011, 1, 1)
    dt = base_date + datetime.timedelta(minutes=keepa_ts)
    return dt.strftime("%Y-%m-%d")

def to_dollars(cents):
    """Convert int cents => '$XX.XX', else 'N/A'."""
    if not isinstance(cents, int) or cents < 0:
        return "N/A"
    return f"${cents / 100:.2f}"

def get_offer_last_stock(offer):
    """Pick last element from stockCSV if valid."""
    arr = offer.get("stockCSV", [])
    if len(arr) < 2:
        return 0
    val = arr[-1]
    return val if (isinstance(val, int) and val > 0) else 0

def get_offer_last_price(offer):
    """Pick second-to-last from offerCSV for the price."""
    arr = offer.get("offerCSV", [])
    if len(arr) < 2:
        return None
    val = arr[-2]
    return val if (isinstance(val, int) and val >= 0) else None

def fetch_seller_info(seller_id):
    """
    Hit Keepa's /seller endpoint, returning { sellerName, sellerLifetimeRatings }, or None.
    """
    url = "https://api.keepa.com/seller"
    params = {
        "key": KEEPA_API_KEY,
        "domain": AMAZON_DOMAIN_ID,
        "seller": seller_id
    }
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return None
    
    data = resp.json()
    sellers_dict = data.get("sellers")
    if not sellers_dict:
        return None
    
    # could be either dict or list
    if isinstance(sellers_dict, dict):
        s = sellers_dict.get(seller_id)
        if not s:
            s = next(iter(sellers_dict.values()), None)
    elif isinstance(sellers_dict, list):
        s = sellers_dict[0] if sellers_dict else None
    else:
        s = None
    
    if not s:
        return None

    seller_name = s.get("sellerName", f"SellerID:{seller_id}")
    rc = s.get("ratingCount", [])
    lifetime = rc[3] if (len(rc) == 4) else 0
    
    return {
        "sellerName": seller_name,
        "sellerLifetimeRatings": lifetime
    }

def build_sellers_table_active(product):
    """
    Return a list of *live (active)* sellers with columns:
       [SellerType, SellerName, ReviewCount, Price, FBAFee, Inventory].
    SellerType can be "Amazon" / "FBA" / "MF".
    FBAFee is taken from stats['fbaFees']['pickAndPackFee'] if the offer isFBA or isAmazon.
    """
    stats = product.get("stats", {})
    offers_all = product.get("offers", [])
    live_order = product.get("liveOffersOrder", [])

    # If the product stats has an FBA fee
    pick_pack_fee = None
    fba_fees = stats.get("fbaFees", {})
    if isinstance(fba_fees, dict):
        pick_pack_fee = fba_fees.get("pickAndPackFee")

    result = []

    for idx in live_order:
        if idx < len(offers_all):
            off = offers_all[idx]
        else:
            continue

        # Determine SellerType
        if off.get("isAmazon", False):
            seller_type = "Amazon"
        elif off.get("isFBA", False):
            seller_type = "FBA"
        else:
            seller_type = "MF"

        # Price
        price_cents = get_offer_last_price(off)
        if not price_cents or price_cents < 0:
            continue  # skip invalid price

        # FBA fee

        fba_fees = product.get("fbaFees", {})
        if isinstance(fba_fees, dict):
            pick_pack_fee = fba_fees.get("pickAndPackFee")
        if (seller_type in ["Amazon", "FBA"]) and pick_pack_fee is not None and pick_pack_fee >= 0:
            fba_fee_str = to_dollars(pick_pack_fee)
        else:
            fba_fee_str = "N/A"


        # Inventory
        stock = get_offer_last_stock(off)
        # If you want sellerName from Keepa’s /seller endpoint, call fetch_seller_info:
        sid = off.get("sellerId", "??")
        info = fetch_seller_info(sid)
        if info:
            actual_seller_name = info["sellerName"]
            review_count = info["sellerLifetimeRatings"]
        else:
            actual_seller_name = sid
            review_count = ""


        row = {
            "SellerType": seller_type,
            "SellerName": actual_seller_name,
            "ReviewCount": review_count,
            "Price": to_dollars(price_cents),
            "FBAFee": fba_fee_str,
            "Inventory": stock
        }
        result.append(row)

    return result

def parse_bsr_times(product):
    """
    Return (current_bsr, bsr_7day, bsr_30day, best_bsr).
    If no valid salesRank data is found, return ("N/A","N/A","N/A","N/A").
    """
    sales_ranks = product.get("salesRanks")
    if not sales_ranks or not isinstance(sales_ranks, dict):
        # Means there's no salesRanks key or it's None/empty => just return
        return ("N/A", "N/A", "N/A", "N/A")

    main_cat = product.get("salesRankReference")
    # If main_cat is missing or not in the dict, let's see if we can fallback to any cat
    if not main_cat or str(main_cat) not in sales_ranks:
        # fallback: pick the first available cat in sales_ranks, if any
        if len(sales_ranks) == 0:
            return ("N/A", "N/A", "N/A", "N/A")
        main_cat_id = next(iter(sales_ranks.keys()))  # pick first cat
    else:
        main_cat_id = str(main_cat)

    arr = sales_ranks.get(main_cat_id, [])
    if len(arr) < 2:
        return ("N/A", "N/A", "N/A", "N/A")

    # parse pairs => [ (timestamp, rank), (timestamp, rank), ... ]
    pairs = []
    for i in range(0, len(arr), 2):
        if i+1 < len(arr):
            t = arr[i]
            r = arr[i+1]
            # rank might be -1 if no data => skip?
            pairs.append((t, r))

    if not pairs:
        return ("N/A", "N/A", "N/A", "N/A")

    # current BSR = last pair's rank
    current_bsr = pairs[-1][1]
    best_bsr = min(x[1] for x in pairs if x[1] > 0) if any(x[1] > 0 for x in pairs) else "N/A"

    final_ts = pairs[-1][0]
    cutoff_7  = final_ts - (7*24*60)   # last 7 days in keepa minutes
    cutoff_30 = final_ts - (30*24*60)  # last 30 days in keepa minutes

    arr7  = [r for (ts, r) in pairs if ts >= cutoff_7]
    arr30 = [r for (ts, r) in pairs if ts >= cutoff_30]

    if arr7:
        avg7 = int(sum(arr7)/len(arr7))
    else:
        avg7 = "N/A"

    if arr30:
        avg30 = int(sum(arr30)/len(arr30))
    else:
        avg30 = "N/A"

    return (current_bsr, avg7, avg30, best_bsr)

def sum_all_stocks(product):
    """Sum stock from each *live* offer + stats["stockAmazon"]."""
    stats = product.get("stats", {})

    # Safely handle missing or null liveOffersOrder
    live_order = product.get("liveOffersOrder")
    if not isinstance(live_order, list):
        live_order = []

    offers_all = product.get("offers", [])
    tot = 0

    for idx in live_order:
        if idx < len(offers_all):
            off = offers_all[idx]
            tot += get_offer_last_stock(off)

    # Also add Amazon stock if available
    amz_stock = stats.get("stockAmazon", 0)
    if isinstance(amz_stock, int) and amz_stock > 0:
        tot += amz_stock

    return tot




def count_competitive_sellers(product):
    """
    'competitive' means last-known price is within 5% or $2 of the lowest.
    """
    stats = product.get("stats", {})
    bb_price = stats.get("buyBoxPrice", -1)
    if bb_price < 0:
        c = stats.get("current")
        if isinstance(c, list) and c and isinstance(c[0], int):
            bb_price = c[0]

    offers = product.get("offers")
    if not isinstance(offers, list):
        offers = []
    last_prices = []
    for off in offers:
        p = get_offer_last_price(off)
        if p and p>0:
            last_prices.append(p)
    if not last_prices:
        return 0
    lowest = min(last_prices)
    thresh = max(200, int(lowest*0.05))

    return sum(1 for p in last_prices if (p - lowest) <= thresh)

def fetch_product_data(asin):
    """
    Main function: 
      1) Fill in your left‐side table data (Pricing, BSR, #Sellers, etc.).
      2) Build the chart arrays for salesRank (from salesRanks), buyBox (from CSV[**18**]),
         and inventory (from each offer's stockCSV).
    """
    base_url = "https://api.keepa.com/product"
    params = {
        "key": KEEPA_API_KEY,
        "domain": AMAZON_DOMAIN_ID,
        "asin": asin,
        "offers": 20,
        "stock": 1,
        "rating": 1,
        "stats": 365,
        "buybox": 1,
        "history": 1
    }
    resp = requests.get(base_url, params=params)
    if resp.status_code != 200:
        return {"error": f"Keepa API request failed: HTTP {resp.status_code}"}
    raw = resp.json()
    if "products" not in raw or not raw["products"]:
        return {"error": "No product data found"}
    
    product = raw["products"][0]
    stats   = product.get("stats", {})

    final_data = {}

    #
    # PART A: The "table #1" fields
    #
    csv_data = product.get("csv", [])
    def last_val(arr):
        return arr[-1] if (len(arr)>=2 and isinstance(arr[-1], int) and arr[-1]>=0) else None
    
    star_val   = last_val(csv_data[16]) if len(csv_data)>16 and isinstance(csv_data[16], list) else None
    rating_val = last_val(csv_data[17]) if len(csv_data)>17 and isinstance(csv_data[17], list) else None
    final_data["Star Rating"]  = "N/A" if star_val   is None else f"{star_val/10:.1f}"
    final_data["Rating Count"] = "N/A" if rating_val is None else str(rating_val)

    # Basic
    final_data["ASIN"]  = product.get("asin","N/A")
    final_data["Title"] = product.get("title","N/A")
    final_data["Brand"] = product.get("brand","N/A")
    cat_tree = product.get("categoryTree", [])
    final_data["Category"] = cat_tree[0].get("name","N/A") if cat_tree else "N/A"

    # BSR
    c_bsr, b7, b30, b_best = parse_bsr_times(product)
    final_data["Ranking"] = {
        "Current": c_bsr,
        "7 Day": b7,
        "30 Days Avg": b30,
        "Best": b_best
    }

    # Pricing
    bb_price = stats.get("buyBoxPrice", -1)
    if bb_price<0:
        c = stats.get("current", [])
        if c and isinstance(c[0], int) and c[0]>=0:
            bb_price = c[0]
    # fallback for 7/30
    p7=-1; p30=-1
    if isinstance(stats.get("avg"), list) and stats["avg"]:
        p7 = stats["avg"][0]
    if isinstance(stats.get("avg30"), list) and stats["avg30"]:
        p30= stats["avg30"][0]

    # best price
    best_price_cents=-1
    mm = stats.get("min", [])
    if mm and isinstance(mm[0], list) and len(mm[0])==2 and isinstance(mm[0][1], int):
        best_price_cents = mm[0][1]

    final_data["Pricing"] = {
        "Current": to_dollars(bb_price),
        "7 Day": to_dollars(p7),
        "30 Days Avg": to_dollars(p30),
        "Best": to_dollars(best_price_cents)
    }

    # # of sellers
    fba = stats.get("offerCountFBA",0)
    mf  = stats.get("offerCountFBM",0)
    tot = stats.get("totalOfferCount",0)



    # Step 1: Try to get the new Buy Box seller ID
    buy_box_seller_id = stats.get("buyBoxSellerId")
    # If none or "-1" / "-2" => check if there's a used buy box
    if not buy_box_seller_id or buy_box_seller_id in ("-1", "-2"):
        used_seller_id = stats.get("buyBoxUsedSellerId")
        if used_seller_id and used_seller_id not in ("", "-1", "-2"):
            buy_box_seller_id = used_seller_id

    # Step 2: If we have a valid ID, fetch the seller info
    if buy_box_seller_id and buy_box_seller_id not in ("-1", "-2", ""):
        info = fetch_seller_info(buy_box_seller_id)
        if info:
            final_data["Seller Name"] = info["sellerName"]
        else:
            # Fallback if API fails
            final_data["Seller Name"] = f"SellerID:{buy_box_seller_id}"
    else:
        # No valid buy box or suppressed/suppressed, so show "N/A" or something
        final_data["Seller Name"] = "No Buy Box"



    is_amz = stats.get("buyBoxIsAmazon", False)

    comp  = count_competitive_sellers(product)
    final_data["# of Sellers"] = {
        "FBA": fba,
        "MF": mf,
        "Competitive": comp,
        "Total": tot,
        "Is Amazon?": "Yes" if is_amz else "No"
    }

    # Inventory
    total_inven = sum_all_stocks(product)  # Now only live
    monthly_sold = product.get("monthlySold", 0)

    if (
        isinstance(monthly_sold, int) and monthly_sold > 0
        and isinstance(b30, int) and b30 > 0
        and isinstance(c_bsr, int) and c_bsr > 0
    ):
        ratio = c_bsr / b30
        adjusted_sold = round(monthly_sold * ratio)
        # Day of Cover
        doc = round((total_inven / adjusted_sold) * 30, 1)
        final_data["Inventory"] = {
            "Day of Cover": doc,
            "Total Inventory": total_inven,
            "Estimated Sales": adjusted_sold
        }
    else:
        final_data["Inventory"] = {
            "Day of Cover": "N/A",
            "Total Inventory": total_inven,
            "Estimated Sales": "N/A"
        }

    # Table #2
    # final_data["Sellers"] = build_sellers_table_only_buybox_sellers(product)

    # Table #2: now list active (live) sellers
    final_data["Sellers"] = build_sellers_table_active(product)

    #
    # PART B: Chart data with { x, y } approach
    #
    from datetime import datetime, timedelta

    def keepa_ts_to_str(ts):
        """Convert keepa minute timestamp => 'YYYY-MM-DD' string."""
        base = datetime(2011,1,1)
        dt = base + timedelta(minutes=ts)
        return dt.strftime("%Y-%m-%d")

    # 1) Sales Rank from product["salesRanks"]
    chart_sales = []
    sr = product.get("salesRanks", {})
    if sr:
        # pick the main cat
        main_cat_id = list(sr.keys())[0]
        sr_arr = sr[main_cat_id]
        # parse pairs
        pairs = []
        for i in range(0, len(sr_arr), 2):
            if i+1 < len(sr_arr):
                pairs.append((sr_arr[i], sr_arr[i+1]))
        # sort by ts
        pairs.sort(key=lambda x: x[0])
        for (ts, rankv) in pairs:
            if rankv >= 0:
                chart_sales.append({
                    "x": keepa_ts_to_str(ts),
                    "y": rankv
                })

    # 2) Buy Box Price - Fetch from CSV[1] instead of CSV[18]
    chart_buybox = []
    csv_all = product.get("csv", [])
    if len(csv_all) > 1 and isinstance(csv_all[1], list):  # Using CSV[1] for new price history
        bb_arr = csv_all[1]  # [timestamp, price, timestamp, price, ...]
        pairs = []
        for i in range(0, len(bb_arr), 2):
            if i+1 < len(bb_arr):
                pairs.append((bb_arr[i], bb_arr[i+1]))
        pairs.sort(key=lambda x: x[0])
        for (ts, price_cents) in pairs:
            if price_cents >= 0:
                chart_buybox.append({
                    "x": keepa_ts_to_str(ts),
                    "y": price_cents / 100.0  # Convert cents to dollars
                })

    # 3) Inventory => for each offer
    chart_inventory = {}
    for off in product.get("offers", []):
        sid = off.get("sellerId", "??")
        st  = off.get("stockCSV", [])
        if len(st) < 2:
            continue
        pairs=[]
        for i in range(0, len(st), 2):
            if i+1<len(st):
                pairs.append((st[i], st[i+1]))
        pairs.sort(key=lambda x: x[0])
        arr=[]
        for (ts, stockval) in pairs:
            if stockval >= 0:
                arr.append({
                    "x": keepa_ts_to_str(ts),
                    "y": stockval
                })
        chart_inventory[sid] = arr

    # store in final_data

    final_data["chartSalesRank"] = chart_sales
    final_data["chartBuyBox"]    = chart_buybox
    final_data["chartInventory"] = chart_inventory
    if not final_data['chartBuyBox']:
        print("no chart")
    if not final_data['chartInventory']:
        print("no inv")

    final_data["__rawKeepaResponse"] = raw

    return final_data