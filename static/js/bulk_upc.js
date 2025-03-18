// static/js/bulk_upc.js

document.addEventListener('DOMContentLoaded', function() {
    const dataEl = document.getElementById('bulkResultsData');
    if (!dataEl) {
      console.warn("No bulkResultsData element found.");
      return;
    }
    try {
      window.bulkResults = JSON.parse(dataEl.textContent);
      console.log("[DEBUG] Bulk results from server:", window.bulkResults);
    } catch (err) {
      console.error("Error parsing bulk results data:", err);
    }
    const cogInput = document.getElementById('costOfGoodsInput');
    if (cogInput) {
        // Listen for “Enter” in that input
        cogInput.addEventListener('keydown', function(e) {
        if (e.key === "Enter") {
            e.preventDefault();
            recalcProfitJS();
        }
        });
    }
  });
  



  
  function recalcProfitJS() {
    // 1) read user input
    const inputEl = document.getElementById('costOfGoodsInput');
    if (!inputEl) return;
    let costOfGoods = parseFloat(inputEl.value) || 0.0;
  
    // 2) loop over the array we originally stored
    if (!window.bulkResults || !Array.isArray(window.bulkResults)) return;
  
    window.bulkResults.forEach((item, index) => {
      // we basically replicate a simpler version of your profit formula
      // or whatever logic you used on the server side:
  
      let lowestPriceStr7  = item.pricing.avg7;
      let lowestPriceStr30 = item.pricing.avg30;
  
      function toNum(str) {
        if (!str || str === "N/A") return 0;
        return parseFloat(str.replace("$","")) || 0;
      }
      let lp7  = toNum(lowestPriceStr7);
      let lp30 = toNum(lowestPriceStr30);
  
      let candidatePrices = [];
      if (lp7 > 0)  candidatePrices.push(lp7);
      if (lp30 > 0) candidatePrices.push(lp30);
  
      if (candidatePrices.length === 0) {
        // fallback to current
        let curVal = toNum(item.pricing.current);
        if (curVal > 0) candidatePrices.push(curVal);
      }
  
      let lowestSellingPrice = candidatePrices.length>0 ? Math.min(...candidatePrices) : 0;
  
      let fbaFee = item.fba_fee || 0;
      let referralFeePct = item.referral_fee_pct || 15.0;
      let referralFee = lowestSellingPrice * (referralFeePct / 100.0);
      
      let profitVal = lowestSellingPrice - fbaFee - referralFee - costOfGoods;


    //   let profitVal = lowestSellingPrice - referralFee - fbaFee - costOfGoods;
      let profitStr = "N/A";
      console.log(
        "DEBUG Profit Calc =>",
        "ASIN:", item.asin,
        "lowestSellingPrice:", lowestSellingPrice,
        'referralFee:', referralFee,
        "fbaFee:", fbaFee,
        "costOfGoods:", costOfGoods
        );  
      if (lowestSellingPrice > 0) {
        let marginPct = (profitVal / lowestSellingPrice)*100;
        profitStr = `$${profitVal.toFixed(2)} (${marginPct.toFixed(1)}%)`;
        if (profitVal <= 0) {
          profitStr = `<span style="color:red">${profitStr}</span>`;
        } else {
          profitStr = `<span style="color:limegreen">${profitStr}</span>`;
        }
      }
  
      // now we update the item’s "profitability" field
      item.profitability = profitStr;
  
      // 3) update the actual <td> in the table
      //    the row index is the same as 'index' in the table’s <tbody>
      let rowEl = document.querySelectorAll('.bulk-results-table tbody tr')[index];
      if (rowEl) {
        // the "Profitability" column is the 4th <td> (0-based index => it's td:nth-child(4) in your <thead>)
        let profitTd = rowEl.querySelectorAll('td')[3];
        if (profitTd) {
          profitTd.innerHTML = profitStr;
        }
      }
    });
  }
  