from flask import Flask, render_template, request, redirect, url_for
import json
from keepa_integration.client import fetch_product_data
from keepa_integration.client_bulk import fetch_bulk_product_data  # New bulk processing function
from keepa_integration.client_bulk import fetch_bulk_product_data_all
from flask import jsonify

app = Flask(__name__)

@app.route('/')
def index():
    """Render the main homepage with options for ASIN and Bulk UPC analysis."""
    return render_template('index.html')

@app.route('/analyze', methods=['GET','POST'])
def analyze():
    """Handle ASIN-based analysis and render the results page."""
    # asin = request.form.get('asin')
    if request.method == 'GET':
        # e.g. from ?asin=...
        asin = request.args.get('asin')
    else:
        # method == 'POST'
        asin = request.form.get('asin')
    if not asin:
        return redirect(url_for('index'))

    product_data = fetch_product_data(asin)

    # Debug: Save raw + final data
    raw_data = product_data.pop("__rawKeepaResponse", None)
    if raw_data:
        with open(f"{asin}_raw.json", "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2)
            print('raw data saved')
    with open(f"{asin}.json", "w", encoding="utf-8") as f:
        json.dump(product_data, f, indent=2)
        print('final data saved')

    return render_template('bulk_analysis.html', product=product_data)

@app.route('/bulk_analysis', methods=['GET', 'POST'])
def bulk_analysis():
    """Handle Bulk UPC Analysis"""
    if request.method == 'POST':
        cogs_input = request.form.get('cog', '').strip()  # read cost-of-goods
        cost_of_goods = float(cogs_input) if cogs_input else 0.0

        upc_input = request.form.get('upc', '').strip()
        if not upc_input:
            return redirect(url_for('index'))

        # Process multiple UPCs (comma-separated)
        upc_list = [upc.strip() for upc in upc_input.split(',') if upc.strip()]
        if not upc_list:
            return redirect(url_for('index'))

        # Fetch bulk product data
        product_list = fetch_bulk_product_data(upc_list)

        # Debug: Save fetched bulk data
        with open("bulk_upc_results.json", "w", encoding="utf-8") as f:
            json.dump(product_list, f, indent=2)

        return render_template('bulk_upc_analysis.html', results=product_list)

    # If GET request, just render an empty table
    return render_template('bulk_upc_analysis.html', results=[])




@app.route('/my_suppliers', methods=['GET'])
def my_suppliers():
    """
    Shows a page listing all the user’s suppliers (read from localStorage in the browser).
    """
    return render_template('my_suppliers.html')

@app.route('/add_supplier', methods=['GET'])
def add_supplier():
    """
    Shows a page where the user can create a new supplier, fill inbound shipping details, and upload a CSV.
    """
    return render_template('add_supplier.html')





@app.route('/fetch_csv_keepa', methods=['POST'])
def fetch_csv_keepa():
    data = request.get_json()
    upc_list = data.get('upcList', [])
    if not upc_list:
        return jsonify([])
    print("[DEBUG] fetch_csv_keepa => upc_list length =", len(upc_list), upc_list)

    # CHANGED: call the chunked function
    results = fetch_bulk_product_data_all(upc_list)
    print("[DEBUG] final results length =", len(results))

    return jsonify(results)



@app.route('/supplier_details')
def supplier_details():
    return render_template('supplier_details.html')




if __name__ == "__main__":
    app.run(debug=True)
