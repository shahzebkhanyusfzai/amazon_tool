// static/js/supplier_details.js

let currentPage = 1;
const pageSize = 20;  // how many rows per page
let upcResults = [];  // array of keepa results
let currentSupplier = null; // store the entire supplier object

document.addEventListener('DOMContentLoaded', () => {
  console.log("[DEBUG supplier_details.js] DOMContentLoaded fired.");

  // 1) Parse ?supplierId=XYZ
  const urlParams = new URLSearchParams(window.location.search);
  const supplierId = urlParams.get('supplierId');
  if (!supplierId) {
    alert("No supplierId specified in URL!");
    return;
  }
  console.log("[DEBUG] supplierId from URL =", supplierId);

  // 2) Load from localStorage
  const suppliers = JSON.parse(localStorage.getItem('suppliers')) || [];
  console.log("[DEBUG] loaded suppliers from LS =>", suppliers);
  
  // 3) Find the matching supplier
  const supplier = suppliers.find(s => s.supplierId === supplierId);
  if (!supplier) {
    alert("Supplier not found in localStorage!");
    return;
  }
  console.log("[DEBUG] Found matching supplier =>", supplier);
  
  currentSupplier = supplier; // store globally so we can reference in recalc

  // 4) The array we fetched from Keepa
  upcResults = supplier.upcKeepaResults || [];
  console.log("[DEBUG] upcKeepaResults =>", upcResults);

  // 5) For each item, do an initial default profit calc if needed
  upcResults.forEach((item, idx) => {
    if (!item.profitability || item.profitability.trim() === "") {
      // Compute a default profitability using the “lowest known price”
      const defaultSellPrice = findLowestPrice(item);
      const breakdown = computeProfitBreakdown(defaultSellPrice, item, supplier);
      // Build final cell string with color, profit, ROI
      item.profitability = buildProfitCellString(breakdown.profit, breakdown.roi, idx);
    }
  });

  // 6) Render the table
  renderPage();
});


// =======================
//  EVENT LISTENER: open the modal on click
// =======================
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('profit-span')) {
    const idx = e.target.getAttribute('data-index');
    console.log("[DEBUG] clicked profit cell => index=", idx);
    showProfitCalculator(idx);
  }
});


// =======================
//  SHOW MODAL + BREAKDOWN
// =======================
function showProfitCalculator(rowIndex) {
  console.log("[DEBUG showProfitCalculator] rowIndex=", rowIndex);
  window.currentCalcRow = rowIndex; // store globally

  // Show the modal
  document.getElementById('profitModal').style.display = 'block';

  // Fill in default Sell Price from item’s lowest price
  const item = upcResults[rowIndex];
  const defaultSell = findLowestPrice(item);
  document.getElementById('modalSellPrice').value = defaultSell.toFixed(2);

  // Also show an *initial* breakdown in the modal (before any user changes)
  const breakdown = computeProfitBreakdown(defaultSell, item, currentSupplier);
  renderProfitBreakdown(breakdown);
}


// =======================
//  CLICK: RECALCULATE in MODAL
// =======================
document.getElementById('recalcBtn').addEventListener('click', () => {
  console.log("[DEBUG] recalcBtn clicked");
  
  const rowIndex = window.currentCalcRow;
  if (rowIndex == null) {
    console.warn("[WARN] rowIndex is null => cannot recalc");
    return;
  }
  const item = upcResults[rowIndex];

  // read user’s new “Sell Price” from modal
  const spVal = document.getElementById('modalSellPrice').value;
  const sellPrice = parseFloat(spVal) || 0;  // treat invalid as 0
  console.log("[DEBUG] recalc => user typed sellPrice=", sellPrice);

  // Compute new breakdown
  const breakdown = computeProfitBreakdown(sellPrice, item, currentSupplier);

  // Update the modal with fresh line items
  renderProfitBreakdown(breakdown);

  // Also update the table cell
  item.profitability = buildProfitCellString(breakdown.profit, breakdown.roi, rowIndex);

  // Re-render just that row in the table
  const rowEl = document.querySelectorAll('#supplierDetailTableBody tr')[rowIndex];
  if (rowEl) {
    // the Profit column is 4th <td>
    rowEl.querySelectorAll('td')[3].innerHTML = item.profitability;
  }
});


// =======================
//  CLICK: close the modal
// =======================
document.getElementById('closeModal').addEventListener('click', () => {
  console.log("[DEBUG] closeModal clicked => hiding modal");
  document.getElementById('profitModal').style.display = 'none';
});


// =======================
//  HELPER: computeProfitBreakdown
// =======================
function computeProfitBreakdown(sellPrice, item, supplier) {
  const costOfGoods      = item.costOfGoods || 0;
  const shippingPerLb    = supplier.inboundShippingPerLb || 0;
  const shippingPct      = supplier.inboundShippingPercent || 0;

  // The portion of inbound shipping that depends on costOfGoods
  const shippingPctAmount = costOfGoods * (shippingPct / 100);

  // The total inbound shipping cost is (per-lb) + (pct-based amount)
  const totalShippingCost = shippingPerLb + shippingPctAmount;

  const fbaFee         = item.fba_fee || 0;
  const referralFeePct = item.referral_fee_pct || 15;

  // Referral fee
  const referralFee = sellPrice * (referralFeePct / 100);

  // Profit
  const profit = sellPrice - referralFee - fbaFee - costOfGoods - totalShippingCost;

  // ROI => now uses (costOfGoods + totalShippingCost) as the cost basis
  let roi = 0;
  const totalCostBasis = costOfGoods + totalShippingCost;
  if (totalCostBasis > 0) {
    roi = (profit / totalCostBasis) * 100;
  }

  return {
    sellPrice,
    costOfGoods,
    referralFeePct,
    referralFee,
    fbaFee,
    shippingPerLb,
    shippingPct,
    shippingPctAmount,
    totalShippingCost,
    profit,
    roi
  };
}


// =======================
//  HELPER: renderProfitBreakdown in the modal
// =======================
function renderProfitBreakdown(bd) {
  const area = document.getElementById('profitResultArea');

  // Color profit / ROI depending on sign
  let profitColor = (bd.profit > 0) ? 'limegreen'
                   : (bd.profit < 0) ? 'red'
                   : 'inherit';
  let roiColor    = (bd.roi > 0) ? 'limegreen'
                   : (bd.roi < 0) ? 'red'
                   : 'inherit';

  area.innerHTML = `
    <h4>Breakdown</h4>
    <table style="width:100%; border-collapse: collapse; color:#ccc;">
      <tr>
        <td style="padding: 4px;">Sell Price</td>
        <td style="padding: 4px; text-align: right;">$${bd.sellPrice.toFixed(2)}</td>
      </tr>
      <tr>
        <td style="padding: 4px;">Referral Fee (${bd.referralFeePct}%)</td>
        <td style="padding: 4px; text-align: right;">-$${bd.referralFee.toFixed(2)}</td>
      </tr>
      <tr>
        <td style="padding: 4px;">FBA Fee</td>
        <td style="padding: 4px; text-align: right;">-$${bd.fbaFee.toFixed(2)}</td>
      </tr>

      <!-- Inbound Shipping (split) -->
      <tr>
        <td style="padding: 4px;">Inbound Shipping (Per-lb)</td>
        <td style="padding: 4px; text-align: right;">-$${bd.shippingPerLb.toFixed(2)}</td>
      </tr>
      <tr>
        <td style="padding: 4px;">Inbound Shipping (${bd.shippingPct}% of Cost)</td>
        <td style="padding: 4px; text-align: right;">-$${bd.shippingPctAmount.toFixed(2)}</td>
      </tr>
      <tr>
        <td style="padding: 4px; font-style:italic;">Total Inbound Shipping</td>
        <td style="padding: 4px; text-align: right; font-style:italic;">-$${bd.totalShippingCost.toFixed(2)}</td>
      </tr>

      <tr>
        <td style="padding: 4px;">Cost of Goods</td>
        <td style="padding: 4px; text-align: right;">-$${bd.costOfGoods.toFixed(2)}</td>
      </tr>

      <tr>
        <td style="padding: 4px; font-weight:bold;">Profit</td>
        <td style="padding: 4px; text-align: right; font-weight:bold; color:${profitColor};">
          $${bd.profit.toFixed(2)}
        </td>
      </tr>
      <tr>
        <td style="padding: 4px; font-weight:bold;">ROI</td>
        <td style="padding: 4px; text-align: right; font-weight:bold; color:${roiColor};">
          ${bd.roi.toFixed(1)}%
        </td>
      </tr>
    </table>
  `;
}


// =======================
//  HELPER: buildProfitCellString (+ROI)
// =======================
function buildProfitCellString(profitValue, roiValue, rowIndex) {
  // ROI and Profit get color-coded
  let color = (profitValue > 0) ? 'limegreen'
            : (profitValue < 0) ? 'red'
            : 'inherit';
  
  const profitStr = `$${profitValue.toFixed(2)}`;
  const roiStr    = `${roiValue.toFixed(1)}%`;

  // Example final: “<span … >$2.50 (25.6%)</span>”
  return `
    <span class="profit-span" data-index="${rowIndex}" style="color:${color}; cursor:pointer;">
      ${profitStr} (${roiStr})
    </span>
  `;
}


// =======================
//  RENDER TABLE
// =======================
function renderPage() {
  console.log("[DEBUG renderPage] currentPage=", currentPage);

  const startIndex = (currentPage - 1) * pageSize;
  const endIndex   = startIndex + pageSize;
  const pageItems  = upcResults.slice(startIndex, endIndex);

  const tbody = document.getElementById('supplierDetailTableBody');
  tbody.innerHTML = '';

  pageItems.forEach((item, index) => {
    const actualIndex = startIndex + index; 
    // actualIndex => the index in upcResults

    // Banana icon logic
    let bananaHtml = '';
    const doc = item.inventory.daysOfCover;
    if (doc === "N/A") {
      bananaHtml = `<img src="/static/img/questionmark.png" alt="?" class="banana-icon">`;
    } else if (parseFloat(doc) <= 15) {
      bananaHtml = `<img src="/static/img/yellow_banana.png" alt="Banana" class="banana-icon">`;
    } else if (parseFloat(doc) <= 22) {
      bananaHtml = `<img src="/static/img/green_banana.png" alt="Banana" class="banana-icon">`;
    } else {
      bananaHtml = `<img src="/static/img/rotten_banana.jpg" alt="Banana" class="banana-icon">`;
    }

    // Title / ASIN / ...
    const titleHtml = `
      <a href="/analyze?asin=${encodeURIComponent(item.asin)}">
        <strong>${item.title}</strong><br>
        ASIN: ${item.asin}<br>
        UPC(s): ${(item.upc || []).join(', ')}<br>
        Rating: ${item.rating.star} (${item.rating.count} reviews)
      </a>`;

    // Price
    const priceHtml = `
      Current: ${item.pricing.current}<br>
      30d: ${item.pricing.avg30}<br>
      90d: ${item.pricing.avg90}
    `;

    // Profit => store or rebuild
    let profitabilityHtml = item.profitability;
    if (!profitabilityHtml) {
      const breakdown = computeProfitBreakdown(0, item, currentSupplier);
      profitabilityHtml = buildProfitCellString(breakdown.profit, breakdown.roi, actualIndex);
      item.profitability = profitabilityHtml;
    }

    // Ranking
    const rankHtml = `
      Current: ${item.ranking.current}<br>
      7d: ${item.ranking.avg7 || '-'}<br>
      30d: ${item.ranking.avg30}
    `;

    // Estimated sales
    const estSales = (item.estimatedSales !== "N/A") ? item.estimatedSales : "N/A";

    // Inventory
    const inventoryHtml = `
      Stock: ${item.inventory.totalStock}<br>
      Days of Cover: ${item.inventory.daysOfCover}
    `;

    // bought in past month
    const bought = (item.boughtInPastMonth !== "N/A") ? item.boughtInPastMonth : "N/A";

    // # Sellers
    const sellerInfo = `
      FBA: ${item['#sellers'].FBA}<br>
      MF: ${item['#sellers'].MF}<br>
      Total: ${item['#sellers'].Total}
    `;

    // Sold by Amazon
    const soldByAmz = item['#sellers'].IsAmazon ? "Yes" : "No";

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${bananaHtml}</td>
      <td>${titleHtml}</td>
      <td>${priceHtml}</td>
      <td>${profitabilityHtml}</td>
      <td>${rankHtml}</td>
      <td>${estSales}</td>
      <td>${inventoryHtml}</td>
      <td>${bought}</td>
      <td>${sellerInfo}</td>
      <td>${soldByAmz}</td>
    `;
    tbody.appendChild(tr);
  });

  // Pagination text
  const pageInfo = document.getElementById('pageInfo');
  const totalPages = Math.ceil(upcResults.length / pageSize);
  pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
}


// =======================
//  PAGINATION
// =======================
function nextPage() {
  const totalPages = Math.ceil(upcResults.length / pageSize);
  if (currentPage < totalPages) {
    currentPage++;
    renderPage();
  }
}
function prevPage() {
  if (currentPage > 1) {
    currentPage--;
    renderPage();
  }
}


// =======================
//  HELPER: findLowestPrice
// =======================
function findLowestPrice(item) {
  // We'll try: current, avg30, avg90, best, etc.
  let prices = [];
  function toNum(str) {
    if (!str || str === "N/A") return 0;
    return parseFloat(str.replace('$','')) || 0;
  }
  prices.push(toNum(item.pricing.current));
  prices.push(toNum(item.pricing.avg30));
  prices.push(toNum(item.pricing.avg90));
  // You could also push item.pricing.best if you want
  // prices.push(toNum(item.pricing.best));

  // Filter out zeros
  const validPrices = prices.filter(p => p > 0);
  if (validPrices.length < 1) {
    return 0; // fallback => 0 if none exist
  }
  return Math.min(...validPrices);
}

