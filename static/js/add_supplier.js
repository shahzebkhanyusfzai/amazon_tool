// static/js/add_supplier.js

function parseCost(str) {
  if (!str) return 0;
  const cleaned = str.trim().replace(/,/g, '');
  const val = parseFloat(cleaned);
  return isNaN(val) ? 0 : val;
}

function saveSupplier() {
  const nameEl = document.getElementById('supplierName');
  const perLbEl = document.getElementById('inboundShippingPerLb');
  const percentEl = document.getElementById('inboundShippingPercent');
  const csvFileEl = document.getElementById('csvFile');

  const supplier = {
    supplierId: generateRandomId(),
    name: nameEl.value.trim(),
    inboundShippingPerLb: parseFloat(perLbEl.value) || 0.0,
    inboundShippingPercent: parseFloat(percentEl.value) || 0.0,
    rawCsv: [],
    upcKeepaResults: []
  };

  if (csvFileEl.files && csvFileEl.files.length > 0) {
    const file = csvFileEl.files[0];
    console.log("[DEBUG add_supplier.js] The user selected file:", file.name, "size=", file.size);

    const reader = new FileReader();

    reader.onload = function (e) {
      // e.target.result is an ArrayBuffer
      const arrayBuffer = e.target.result;
      console.log("[DEBUG add_supplier.js] FileReader onload => got arrayBuffer of size:", arrayBuffer.byteLength);

      // Convert to a Uint8Array for XLSX:
      const data = new Uint8Array(arrayBuffer);

      try {
        const workbook = XLSX.read(data, { type: "array" });
        
        // Grab first sheet
        const sheetName = workbook.SheetNames[0];
        console.log("[DEBUG add_supplier.js] Found sheetName =", sheetName);

        const ws = workbook.Sheets[sheetName];

        // Convert to a 2D array (array of arrays)
        const aoa = XLSX.utils.sheet_to_json(ws, { header: 1 });
        supplier.rawCsv = aoa;

        console.log("[DEBUG add_supplier.js] => aoa.length =", aoa.length);

        // Build a dictionary: upc => cost
        const upcCostMap = {};

        // We'll also keep a small array to see raw row debugging
        // so you can see how each row is processed
        let rowCounter = 0;

        aoa.forEach((row, idx) => {
          // row is something like: [ upcCandidate, costCandidate, ... ]
          console.log(`[DEBUG] Row #${idx} =>`, row);

          if (row.length < 1) {
            console.log(`[DEBUG] Row #${idx} => has no cells; skipping`);
            return;
          }

          const firstCell = row[0];
          if (!firstCell) {
            console.log(`[DEBUG] Row #${idx} => row[0] is empty => skip`);
            return;
          }

          let upcCandidate = normalizeUpcString(firstCell);
          console.log(`[DEBUG] Row #${idx} => upcCandidate after normalize=`, upcCandidate);

          if (row.length >= 2) {
            let costCandidate = (row[1] || '').toString().trim();
            const costVal = parseCost(costCandidate);
            console.log(`[DEBUG] Row #${idx} => costCandidate=[${costCandidate}] => costVal=`, costVal);

            if (upcCandidate) {
              upcCostMap[upcCandidate] = costVal;
            }
          } else {
            console.log(`[DEBUG] Row #${idx} => No second column => no cost found`);
          }
        });

        // Now build a unique set of cleaned UPCs
        const upcSet = new Set();
        aoa.forEach((row, idx) => {
          if (row[0]) {
            let upcCandidate = normalizeUpcString(row[0]);
            if (upcCandidate) {
              upcSet.add(upcCandidate);
            }
          }
        });
        const upcList = Array.from(upcSet);

        console.log("[DEBUG add_supplier.js] => upcSet final size =", upcSet.size, " => upcList =>", upcList);
        console.log("[DEBUG add_supplier.js] => upcCostMap =>", upcCostMap);

        document.getElementById('uploadSpinner').style.display = 'block';
        console.log("About to POST to /fetch_csv_keepa with upcList.length=", upcList.length);

        fetch('/fetch_csv_keepa', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ upcList })
        })
          .then(resp => resp.json())
          .then(data => {
            document.getElementById('uploadSpinner').style.display = 'none';
            console.log("[DEBUG] /fetch_csv_keepa => received array of length:", data.length);

            data.forEach(item => {
              let costFound = 0;
              if (Array.isArray(item.upc)) {
                for (let singleUpc of item.upc) {
                  if (upcCostMap[singleUpc] !== undefined) {
                    costFound = upcCostMap[singleUpc];
                    break;
                  }
                }
              }
              item.costOfGoods = costFound;
            });
            supplier.upcKeepaResults = data;
            storeSupplierAndRedirect(supplier);
          })
          .catch(err => {
            console.error("Error fetching Keepa data:", err);
            document.getElementById('uploadSpinner').style.display = 'none';
            storeSupplierAndRedirect(supplier);
          });
      } catch (err) {
        console.error("[DEBUG add_supplier.js] XLSX read/parse error =>", err);
        alert("SheetJS parse error! See console for details.");
      }
    };

    // Instead of readAsBinaryString, use readAsArrayBuffer:
    reader.readAsArrayBuffer(file);

  } else {
    // No file selected => store supplier anyway
    console.log("[DEBUG add_supplier.js] => No CSV file selected => just storing supplier with no upcKeepaResults");
    storeSupplierAndRedirect(supplier);
  }
}


function storeSupplierAndRedirect(supplier) {
  console.log("[DEBUG storeSupplierAndRedirect] => final supplier object =>", supplier);
  let allSuppliers = JSON.parse(localStorage.getItem('suppliers')) || [];
  allSuppliers.push(supplier);
  localStorage.setItem('suppliers', JSON.stringify(allSuppliers));
  window.location.href = '/my_suppliers';
}

function generateRandomId() {
  return 'sup-' + Date.now() + '-' + Math.floor(Math.random() * 10000);
}

function normalizeUpcString(upcCandidate) {
  // Convert everything to a string
  let str = String(upcCandidate || '');
  let raw = str.trim().replace(/"/g, '');

  // debug
  // console.log("[DEBUG normalizeUpcString] raw =>", raw);

  // If the cell has scientific notation, parse it
  if (/e|E/.test(raw)) {
    let parsed = parseFloat(raw);
    if (!isNaN(parsed)) {
      return parsed.toFixed(0);
    }
  }

  return raw;
}
