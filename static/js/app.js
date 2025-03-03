let myChart = null;

// Store full dataset for filtering
window.fullData = null; 
window.currentGraph = "salesRank"; // Default graph to Sales Rank

if (!window.chartData || Object.keys(window.chartData).length === 0) {
  console.error("🚨 chartData is EMPTY before initializing Chart!");
} else {
  console.log("✅ chartData is READY:", window.chartData);
  window.fullData = JSON.parse(JSON.stringify(window.chartData)); // Store full dataset
}

function initAnalysisChart() {
  console.log("[DEBUG] Chart data from server:", window.chartData);

  const ctx = document.getElementById("analysisChart").getContext("2d");

  // ✅ Destroy existing chart before creating a new one
  if (myChart) {
    myChart.destroy();
    console.log("🔥 Destroyed previous chart instance.");
  }

  myChart = null; // Ensure it gets re-initialized properly

  // Extract datasets based on current graph selection
  let datasets = [];

  if (window.currentGraph === "salesRank") {
    datasets.push({
      label: "Sales Rank",
      data: window.chartData.chartSalesRank || [],
      borderColor: "red",
      backgroundColor: "rgba(255,0,0,0.2)",
      stepped: true,
      fill: true,
      hidden: false
    });
  } else if (window.currentGraph === "buyBox") {
    datasets.push({
      label: "Buy Box",
      data: window.chartData.chartBuyBox || [],
      borderColor: "blue",
      backgroundColor: "rgba(0,0,255,0.2)",
      stepped: true,
      fill: true,
      hidden: false
    });
  } else if (window.currentGraph === "inventory") {
    let colorPool = ["green", "orange", "purple", "blue", "maroon", "teal", "magenta"];
    let cIndex = 0;

    const invObj = window.chartData.chartInventory || {};
    for (let sellerId in invObj) {
      let brandName = window.fullData.brand || "Unknown Brand"; // ✅ Use existing brand field

      datasets.push({
        label: sellerId,
        data: invObj[sellerId],
        borderColor: colorPool[cIndex % colorPool.length],
        backgroundColor: "rgba(179, 206, 179, 0.2)", // Light green for inventory
        stepped: true,
        fill: true,
        hidden: false
      });
      cIndex++;
    }
  }


  let yAxisTitle = "Value"; // Default
  if (window.currentGraph === "salesRank") yAxisTitle = "BSR";
  if (window.currentGraph === "buyBox") yAxisTitle = "Buy Box Price ($)";
  if (window.currentGraph === "inventory") yAxisTitle = "Stock (Units)";




  // ✅ Ensure datasets are not empty
  console.log("✅ Current Graph:", window.currentGraph);
  console.log("✅ Data for Graph:", datasets);




  // ✅ Fix X-Axis scale issue (keep 'time')
  myChart = new Chart(ctx, {
    type: "line",
    data: { datasets },
    options: {
      responsive: true,
      scales: {
        x: {
          type: "time",
          time: {
            parser: "YYYY-MM-DD",
            unit: "day",
            tooltipFormat: "YYYY-MM-DD",
            displayFormats: { day: "YYYY-MM-DD" }
          },
          title: { display: true, text: "Date" }
        },
        y: { title: { display: true, text: yAxisTitle } }
      }
    }
  });

  console.log("✅ Chart successfully initialized!");
}

// ✅ Toggle between graphs without affecting date range
function toggleGraph(type) {
  window.currentGraph = type;
  initAnalysisChart();
}

// ✅ Apply Date Range Filter only to the Active Graph
function setDateRange(days) {
  if (!window.fullData) return;
  
  console.log(`🔄 Filtering ${window.currentGraph} data for last ${days} days`);

  // ❗️ We need to handle “inventory” differently since it’s an object of arrays.
  let lastDateObj = null;

  if (window.currentGraph === "inventory") {
    // Gather ALL points from all sellers, find the most recent date
    let allSellersData = Object.values(window.fullData.chartInventory).flat();
    if (!allSellersData || allSellersData.length < 1) {
      console.warn("⚠️ No inventory data to filter!");
      return;
    }
    // Sort by date so we can pick the last one
    allSellersData.sort((a, b) => new Date(a.x) - new Date(b.x));
    let lastDateStr = allSellersData[allSellersData.length - 1].x;
    lastDateObj = new Date(lastDateStr + "T00:00:00");
  } else {
    // salesRank or buyBox (each is just one array)
    const activeDataset = window.fullData[`chart${capitalize(window.currentGraph)}`];
    if (!activeDataset || activeDataset.length < 1) {
      console.warn("⚠️ No data to filter for", window.currentGraph);
      return;
    }
    let lastDateStr = activeDataset[activeDataset.length - 1].x;  
    lastDateObj = new Date(lastDateStr + "T00:00:00");
  }

  // Compute cutoff date
  const cutoffDateObj = new Date(lastDateObj.getTime() - (days * 24 * 3600 * 1000));

  // ❗️ Now do the actual filter
  if (window.currentGraph === "salesRank") {
    // Filter the array
    window.chartData.chartSalesRank = window.fullData.chartSalesRank.filter(pt => {
      let d = new Date(pt.x + "T00:00:00");
      return d >= cutoffDateObj;
    });
  } else if (window.currentGraph === "buyBox") {
    // Filter the array
    window.chartData.chartBuyBox = window.fullData.chartBuyBox.filter(pt => {
      let d = new Date(pt.x + "T00:00:00");
      return d >= cutoffDateObj;
    });
  } else if (window.currentGraph === "inventory") {
    // Filter each seller separately
    Object.keys(window.fullData.chartInventory).forEach(sid => {
      let sellerData = window.fullData.chartInventory[sid];
      if (Array.isArray(sellerData) && sellerData.length > 0) {
        window.chartData.chartInventory[sid] = sellerData.filter(pt => {
          return pt && pt.x && new Date(pt.x + "T00:00:00") >= cutoffDateObj;
        });
      } else {
        console.warn(`⚠️ No inventory data for seller ${sid} or data is malformed`);
        window.chartData.chartInventory[sid] = []; // Ensure it's empty if missing
      }
    });
  }

  // ✅ Rebuild chart with the filtered data
  initAnalysisChart();
}

// ✅ Utility function to capitalize the first letter
function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
