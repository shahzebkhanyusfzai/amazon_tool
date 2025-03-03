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

def build_sellers_table_only_buybox_sellers(product):
    """
    Just like your original approach: gather any seller in stats["buyBoxStats"] / buyBoxUsedStats,
    find the matching 'offer' for that seller to get last-known price, stock, etc.
    """
    stats = product.get("stats", {})
    bbs    = stats.get("buyBoxStats", {})
    bbs_used = stats.get("buyBoxUsedStats", {})
    seller_ids = set(bbs.keys()) | set(bbs_used.keys())

    offers_by_seller = {}
    for off in product.get("offers", []):
        sid = off.get("sellerId")
        if sid:
            offers_by_seller[sid] = off

    result = []
    for sid in seller_ids:
        off = offers_by_seller.get(sid)
        if not off:
            continue
        price_cents = get_offer_last_price(off)
        if not price_cents or price_cents <= 0:
            continue

        row = {}
        info = fetch_seller_info(sid)
        if info:
            row["SellerName"]  = info["sellerName"]
            row["ReviewCount"] = info["sellerLifetimeRatings"]
        else:
            row["SellerName"]  = f"SellerID: {sid}"
            row["ReviewCount"] = ""

        row["Price"] = to_dollars(price_cents)
        row["Inventory"] = get_offer_last_stock(off)
        
        # FBA fee if isFBA
        is_fba = off.get("isFBA", False)
        pick_pack_fee = stats.get("fbaFees", {}).get("pickAndPackFee")
        if is_fba and isinstance(pick_pack_fee, int) and pick_pack_fee > 0:
            row["FBAFee"] = to_dollars(pick_pack_fee)
        else:
            row["FBAFee"] = "N/A"

        result.append(row)

    return result

def parse_bsr_times(product):
    """
    Return (current_bsr, bsr_7day, bsr_30day, best_bsr), reading from product["salesRanks"].
    """
    sales_ranks = product.get("salesRanks", {})
    main_cat = product.get("salesRankReference")
    if not main_cat or str(main_cat) not in sales_ranks:
        # fallback
        if sales_ranks:
            main_cat = list(sales_ranks.keys())[0]
        else:
            return ("N/A", "N/A", "N/A", "N/A")

    arr = sales_ranks[str(main_cat)]
    if len(arr) < 2:
        return ("N/A", "N/A", "N/A", "N/A")

    # pairs
    pairs = []
    for i in range(0, len(arr), 2):
        if i+1 < len(arr):
            pairs.append((arr[i], arr[i+1]))
    if not pairs:
        return ("N/A", "N/A", "N/A", "N/A")

    current_bsr = pairs[-1][1]
    best_bsr    = min(x[1] for x in pairs)
    
    final_ts = pairs[-1][0]
    cutoff_7  = final_ts - (7*24*60)
    cutoff_30 = final_ts - (30*24*60)

    arr7 = [r for (ts, r) in pairs if ts >= cutoff_7]
    arr30= [r for (ts, r) in pairs if ts >= cutoff_30]
    avg7 = int(sum(arr7)/len(arr7)) if arr7 else "N/A"
    avg30= int(sum(arr30)/len(arr30)) if arr30 else "N/A"

    return (current_bsr, avg7, avg30, best_bsr)

def sum_all_stocks(product):
    """
    Sum stock from each offer + stats["stockAmazon"] if any.
    """
    tot = 0
    for off in product.get("offers", []):
        tot += get_offer_last_stock(off)
    stats = product.get("stats", {})
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

    offers = product.get("offers", [])
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
    if isinstance(stats.get("avg7"), list) and stats["avg7"]:
        p7 = stats["avg7"][0]
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
    is_amz = stats.get("buyBoxIsAmazon", False)
    comp  = count_competitive_sellers(product)
    final_data["# of Sellers"] = {
        "FBA": fba,
        "MF": mf,
        "Competitive": comp,
        "Total": tot,
        "Is Amazon?": "Yes" if is_amz else "No"
    }
    final_data["Seller Name"] = "Amazon" if is_amz else "3rd Party"

    # Inventory
    total_inven = sum_all_stocks(product)
    monthly_sold= product.get("monthlySold", 0)
    if not isinstance(monthly_sold, int) or monthly_sold<=0:
        final_data["Inventory"] = {
            "Day of Cover":"N/A",
            "Total Inventory": total_inven,
            "Estimated Sales":"N/A"
        }
    else:
        doc = round((total_inven/monthly_sold)*30,1)
        final_data["Inventory"] = {
            "Day of Cover": doc,
            "Total Inventory": total_inven,
            "Estimated Sales": monthly_sold
        }

    # Table #2
    final_data["Sellers"] = build_sellers_table_only_buybox_sellers(product)

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

    # # 2) Buy Box from CSV[18] => new buy box price history 
    # chart_buybox = []
    # csv_all = product.get("csv", [])
    # if len(csv_all) > 18 and isinstance(csv_all[18], list):
    #     bb_arr = csv_all[18]  # [ts, price, ts, price, ...]
    #     pairs = []
    #     for i in range(0, len(bb_arr), 2):
    #         if i+1 < len(bb_arr):
    #             pairs.append((bb_arr[i], bb_arr[i+1]))
    #     pairs.sort(key=lambda x: x[0])
    #     for (ts, price_cents) in pairs:
    #         if price_cents >= 0:
    #             chart_buybox.append({
    #                 "x": keepa_ts_to_str(ts),
    #                 "y": price_cents / 100.0
    #             })
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
    return final_data