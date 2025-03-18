// static/js/add_supplier.js

function saveSupplier() {
    const nameEl = document.getElementById("supplierName");
    const perLbEl = document.getElementById("inboundShippingPerLb");
    const pctEl   = document.getElementById("inboundShippingPercent");
    const csvFileEl = document.getElementById("csvFile");
  
    const supplier = {
      supplierId: generateRandomId(),
      name: nameEl.value.trim(),
      inboundShippingPerLb: parseFloat(perLbEl.value) || 0.0,
      inboundShippingPercent: parseFloat(pctEl.value) || 0.0,
      rawCsv: [],
      upcKeepaResults: []
    };
  
    console.log("[DEBUG add_supplier.js] => Creating supplier object:", supplier);
  
    // If no file, just store the supplier as-is
    if (!csvFileEl.files || csvFileEl.files.length === 0) {
      console.log("[DEBUG add_supplier.js] => No CSV selected => storing supplier w/o CSV data");
      storeSupplierAndRedirect(supplier);
      return;
    }
  
    // We have a CSV file => parse it
    const file = csvFileEl.files[0];
    const reader = new FileReader();
  
    reader.onload = function (e) {
      const csvContent = e.target.result || "";
      // 1) Split lines by newline, ignoring empty
      const lines = csvContent.split(/\r?\n/).filter(line => line.trim() !== "");
      console.log(`[DEBUG add_supplier.js] => lines read from CSV: count=${lines.length}`);
      console.log(lines);
  
      // 2) Build supplier.rawCsv for reference
      supplier.rawCsv = lines.map(line => {
        console.log("[DEBUG] raw CSV line =>", line);
        const rowArr = line.split(",");
        console.log("[DEBUG] after .split =>", rowArr);
        return rowArr;
      });
  
      // 3) Build upcCostMap => { upcString: costNumber }
      const upcCostMap = {};
  
      supplier.rawCsv.forEach((row, rowIndex) => {
        if (row.length >= 2) {
          // FIRST column => possible multiple UPCs
          let firstCell = row[0].trim();
          // Remove leading/trailing quotes
          firstCell = firstCell.replace(/^"+/, "").replace(/"+$/, "");
  
          // If user typed something like: `UPC1, UPC2, UPC3`
          // Let's split by commas or spaces
          const possibleUpcs = firstCell.split(/[\s,]+/).filter(Boolean);
  
          // SECOND column => the cost
          const costRaw = row[1].trim();
          const costVal = parseCost(costRaw);
  
          // For debugging
          console.log(`[DEBUG rowIndex=${rowIndex}] multi-UPC parse =>`, possibleUpcs, "costVal=", costVal);
  
          // For each UPC found in the first cell => store cost
          possibleUpcs.forEach(u => {
            // Remove stray quotes if any remain
            const cleanedUpc = u.replace(/^"+/, "").replace(/"+$/, "");
            if (cleanedUpc) {
              upcCostMap[cleanedUpc] = costVal;
            }
          });
        }
      });
  
      console.log("[DEBUG] final upcCostMap =>", upcCostMap);
  
      // 4) Build upcList for Keepa => all distinct UPCs
      const upcSet = new Set(Object.keys(upcCostMap));
      const upcList = Array.from(upcSet);
      console.log("[DEBUG] final upcList =>", upcList);
  
      // 5) Show spinner, call /fetch_csv_keepa
      document.getElementById("uploadSpinner").style.display = "block";
  
      fetch("/fetch_csv_keepa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upcList })
      })
        .then(resp => resp.json())
        .then(data => {
          console.log("[DEBUG] /fetch_csv_keepa => returned data =>", data);
          document.getElementById("uploadSpinner").style.display = "none";
  
          // For each returned Keepa item => find costOfGoods
          data.forEach(item => {
            let foundCost = 0;
            // item.upc => array of possible UPC strings
            if (Array.isArray(item.upc)) {
              for (const possibleUpc of item.upc) {
                if (upcCostMap[possibleUpc] !== undefined) {
                  foundCost = upcCostMap[possibleUpc];
                  break; // Stop if found
                }
              }
            }
            item.costOfGoods = foundCost;
          });
  
          supplier.upcKeepaResults = data;
          storeSupplierAndRedirect(supplier);
        })
        .catch(err => {
          console.error("[ERROR] => /fetch_csv_keepa failed =>", err);
          document.getElementById("uploadSpinner").style.display = "none";
          storeSupplierAndRedirect(supplier); // fallback
        });
    };
  
    reader.readAsText(file);
  }
  
  /**
   * parseCost - normalizes a string to handle commas, quotes, scientific notation, etc.
   * e.g. "1,234.56" => 1234.56
   * e.g. "1.23e2" => 123
   */
  function parseCost(str) {
    if (!str) return 0;
    // Remove quotes
    str = str.replace(/"/g, "");
    // Remove commas
    str = str.replace(/,/g, "").trim();
    // Then parse as float (JS can interpret standard scientific notation)
    const val = parseFloat(str);
    return isNaN(val) ? 0 : val;
  }
  
  function storeSupplierAndRedirect(supplier) {
    console.log("[DEBUG storeSupplierAndRedirect] => final supplier =>", supplier);
    let allSuppliers = JSON.parse(localStorage.getItem("suppliers")) || [];
    allSuppliers.push(supplier);
    localStorage.setItem("suppliers", JSON.stringify(allSuppliers));
    window.location.href = "/my_suppliers";
  }
  
  function generateRandomId() {
    return "sup-" + Date.now() + "-" + Math.floor(Math.random() * 10000);
  }
  