# Amazon Analysis Tool

This **Amazon Analysis Tool** is a custom web application built with [Flask](https://flask.palletsprojects.com/) for scraping and analyzing Amazon data via [Keepa’s API](https://keepa.com/#!api). It provides:

- **Single-ASIN Analysis**: Deep-dive charting of BuyBox, sales rank, and inventory.  
- **Bulk UPC Analysis**: Lookup multiple UPC codes at once, fetching Keepa product data.  
- **Supplier Management**: Upload a supplier CSV (UPC + cost) and store data in the browser’s localStorage.  
- **Profit Calculation**: Visual per-item profit & ROI calculator.

---

## Table of Contents

1. [Key Features](#key-features)  
2. [Project Structure](#project-structure)  
3. [Getting Started](#getting-started)  
   - [Prerequisites](#prerequisites)  
   - [Installation](#installation)  
   - [Running the App](#running-the-app)  
4. [Usage](#usage)  
   - [ASIN Analysis](#asin-analysis)  
   - [Bulk Analysis via UPC](#bulk-analysis-via-upc)  
   - [Managing Suppliers](#managing-suppliers)  
   - [Deep-Dive Charts & Graphs](#deep-dive-charts--graphs)  
5. [Data Flow / Architecture](#data-flow--architecture)  
6. [Customizing & Extending](#customizing--extending)  
7. [Troubleshooting](#troubleshooting)  
8. [License](#license)

---

## Key Features

- **Single ASIN “Deep Dive”**  
  Enter an ASIN to fetch real-time data from Keepa (price history, BSR, sellers, inventory) and display them in charts.

- **Bulk UPC Analysis**  
  Enter multiple UPCs (comma-separated) for automated data fetching and a summarized view (current price, sales rank, inventory, Amazon presence, etc.).

- **Supplier CSV Upload**  
  Allows adding new suppliers and uploading a CSV containing UPC codes & cost prices. Data is stored in the browser’s `localStorage`; Keepa calls are performed to gather product info.

- **Profit Calculator**  
  Each product row has a dynamic “Profitability” column (with color-coded profit/ROI). Users can open a modal to recalculate profit based on updated cost, shipping cost, etc.

- **LocalStorage-Based Supplier Management**  
  Add, list, or delete suppliers. Supplier data (CSV, inbound shipping fees) is stored in browser `localStorage` — no external DB needed.

- **Charts**  
  Leverages [Chart.js](https://www.chartjs.org/) to visualize time-series data for Sales Rank, Buy Box, and inventory across different sellers.

---

## Project Structure

```text
======================================
amazon_tool/
├── bin/
│   ├── activate
│   ├── activate.csh
│   ├── activate.fish
│   ├── Activate.ps1
│   ├── flask
│   ├── gunicorn
│   ├── normalizer
│   ├── pip
│   ├── pip3
│   ├── pip3.12
│   ├── python
│   ├── python3
│   └── python3.12

keepa_integration/
├── client_bulk.py        # Bulk UPC processing with Keepa API
└── client.py             # Single ASIN processing with Keepa API

static/
├── css/
│   └── style.css         # Main stylesheet
├── img/
│   ├── green_banana.png
│   ├── green_banana1.png
│   ├── questionmark.png
│   ├── rotten_banana.jpg
│   ├── rotten_banana1.jpg
│   ├── spinner.gif
│   └── yellow_banana.png
└── js/
    ├── add_supplier.js       # Handles supplier CSV upload and parsing
    ├── app.js                # Charts logic (sales rank, buy box, inventory)
    ├── bulk_upc.js           # Handles profit calc for bulk UPC view
    ├── supplier_details.js   # Supplier-specific logic + pagination
    └── suppliers.js          # Supplier list handling (localStorage)

templates/
├── add_supplier.html         # Upload supplier CSV
├── base.html                 # Main layout template
├── bulk_analysis.html        # ASIN analysis view
├── bulk_upc_analysis.html    # Bulk UPC results view
├── index.html                # Home page with ASIN/UPC input
├── my_suppliers.html         # Local supplier management
└── supplier_details.html     # Details per supplier (w/ profit modal)

app.py                        # Flask routes and main app logic
config.py                     # Keepa API key and Amazon domain config
requirements.txt              # Python dependency list
======================================
```
# Getting Started

## Prerequisites
- **Python 3.8+** (recommended)
- A **Keepa API Key** (subscription from [keepa.com](https://keepa.com/#!api))
- **Pip** for installing Python packages

## Installation

**Clone or download** this repository:
   ```bash
   git clone https://github.com/YourUsername/amazon_analysis_tool.git
   cd amazon_analysis_tool

**Create a Virtual Environment (Optional but Recommended)**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or on Windows:
.\venv\Scripts\activate


