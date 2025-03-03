from flask import Flask, render_template, request, redirect, url_for
import json
from keepa_integration.client import fetch_product_data

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    asin = request.form.get('asin')
    if not asin:
        return redirect(url_for('index'))

    product_data = fetch_product_data(asin)

    # # Debug: save raw + final data
    # raw_data = product_data.pop("__rawKeepaResponse", None)
    # if raw_data:
    #     with open(f"{asin}_raw.json", "w", encoding="utf-8") as f:
    #         json.dump(raw_data, f, indent=2)
    # with open(f"{asin}.json", "w", encoding="utf-8") as f:
    #     json.dump(product_data, f, indent=2)

    return render_template('bulk_analysis.html', product=product_data)

if __name__ == "__main__":
    app.run(debug=True)
