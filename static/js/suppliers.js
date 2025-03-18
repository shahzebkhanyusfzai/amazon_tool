// static/js/suppliers.js

document.addEventListener('DOMContentLoaded', function() {
    // 1) Fetch from localStorage
    const suppliers = JSON.parse(localStorage.getItem('suppliers')) || [];
  
    // 2) Grab <ul> for listing
    const suppliersList = document.getElementById('suppliersList');
    suppliersList.innerHTML = '';
  
    // 3) For each supplier, build an <li> that shows:
    //    - Supplier name (click => /supplier_details)
    //    - "Delete" button
    suppliers.forEach((supplier, index) => {
      // Create <li>
      const li = document.createElement('li');
      li.style.margin = '0.5rem 0';
      li.style.listStyle = 'none';
  
      // The name is clickable => leads to supplier_details
      const nameSpan = document.createElement('span');
      nameSpan.textContent = supplier.name || ('Unnamed Supplier #' + index);
      nameSpan.style.cursor = 'pointer';
      nameSpan.addEventListener('click', () => {
        window.location.href = `/supplier_details?supplierId=${supplier.supplierId}`;
      });
  
      // Add the "Delete" button
      const deleteBtn = document.createElement('button');
      deleteBtn.textContent = 'Delete';
      deleteBtn.className = 'bulk-analysis-btn';
      deleteBtn.style.marginLeft = '1rem';
  
      // This prevents clicking delete from also triggering the nameSpan click
      deleteBtn.addEventListener('click', (event) => {
        event.stopPropagation(); 
        const confirmed = confirm(
          `Are you sure you want to delete supplier "${supplier.name}"?\nThis will remove all CSV data too.`
        );
        if (confirmed) {
          removeSupplierById(supplier.supplierId);
        }
      });
  
      // Append both the name and the button to <li>
      li.appendChild(nameSpan);
      li.appendChild(deleteBtn);
  
      // Then append <li> to our <ul>
      suppliersList.appendChild(li);
    });
  });
  
  /**
   * removeSupplierById - remove the supplier from localStorage by ID
   */
  function removeSupplierById(supplierId) {
    let allSuppliers = JSON.parse(localStorage.getItem('suppliers')) || [];
    // Filter out the one we want to delete
    allSuppliers = allSuppliers.filter(sup => sup.supplierId !== supplierId);
    
    // Save back to localStorage
    localStorage.setItem('suppliers', JSON.stringify(allSuppliers));
    
    // Reload so changes reflect immediately
    location.reload();
  }
  