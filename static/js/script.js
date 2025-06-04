document.addEventListener('DOMContentLoaded', () => {
    const placeOrderForm = document.getElementById('placeOrderForm');
    const orderMessageDiv = document.getElementById('orderMessage');
    const portfolioDetailsDiv = document.getElementById('portfolioDetails');
    const orderDetailsDiv = document.getElementById('orderDetails');
    const getQuoteForm = document.getElementById('getQuoteForm');
    const quoteResultDiv = document.getElementById('quoteResult');

    // New elements for account summary
    const initialCapitalEl = document.getElementById('initialCapital');
    const overallPnLEl = document.getElementById('overallPnL');
    const currentEquityEl = document.getElementById('currentEquity');
    const refreshAccountSummaryBtn = document.getElementById('refreshAccountSummary');

    // Existing refresh buttons
    const refreshPortfolioBtn = document.getElementById('refreshPortfolio');
    const refreshOrdersBtn = document.getElementById('refreshOrders');

    const API_BASE_URL = window.location.origin; // Dynamically get the base URL

    // --- Helper Functions ---
    async function fetchData(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching data:', error);
            return { status: 'error', msg: error.message };
        }
    }

    function showMessage(element, message, type = 'info') {
        element.textContent = message;
        element.className = 'mt-4 text-center text-sm font-medium'; // Reset classes
        if (type === 'success') {
            element.classList.add('text-green-600');
        } else if (type === 'error') {
            element.classList.add('text-red-600');
        } else {
            element.classList.add('text-gray-600');
        }
    }

    // --- Order Placement ---
    placeOrderForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(placeOrderForm);
        const params = new URLSearchParams(formData).toString();

        showMessage(orderMessageDiv, 'Placing order...', 'info');

        const response = await fetchData(`${API_BASE_URL}/getOrder?${params}`);

        if (response.status === 'error') {
            showMessage(orderMessageDiv, `Order failed: ${response.msg}`, 'error');
        } else {
            showMessage(orderMessageDiv, `Order placed successfully for ${response.symbol} (Qty: ${response.quantity})!`, 'success');
            placeOrderForm.reset(); // Clear the form
            // Refresh all relevant sections after an order
            fetchAccountSummary();
            fetchPortfolioDetails();
            fetchOrderDetails();
        }
    });

    // --- Account Summary ---
    async function fetchAccountSummary() {
        initialCapitalEl.textContent = 'Loading...';
        overallPnLEl.textContent = 'Loading...';
        currentEquityEl.textContent = 'Loading...';

        const data = await fetchData(`${API_BASE_URL}/portfolioDetails`);

        if (data.status === 'error') {
            initialCapitalEl.textContent = 'Error';
            overallPnLEl.textContent = 'Error';
            currentEquityEl.textContent = 'Error';
            return;
        }

        const initialCapital = data.initialCapital || 0;
        let totalUnrealizedPL = 0;

        if (data.holdings && data.holdings.length > 0) {
            data.holdings.forEach(holding => {
                const currentPrice = data.marketPrices[holding.symbol] || holding.entryPrice; // Fallback if no live quote
                let pnl;
                pnl = (currentPrice - holding.entryPrice) * holding.quantity;


                totalUnrealizedPL += pnl;
            });
        }

        const currentEquity = initialCapital + totalUnrealizedPL;

        initialCapitalEl.textContent = `₹${initialCapital.toFixed(2)}`;
        overallPnLEl.textContent = `₹${totalUnrealizedPL.toFixed(2)}`;
        overallPnLEl.classList.remove('text-green-800', 'text-red-800', 'text-gray-800');
        if (totalUnrealizedPL >= 0) {
            overallPnLEl.classList.add('text-green-800');
        } else {
            overallPnLEl.classList.add('text-red-800');
        }

        currentEquityEl.textContent = `₹${currentEquity.toFixed(2)}`;
    }
    refreshAccountSummaryBtn.addEventListener('click', fetchAccountSummary);


    // --- Portfolio Details ---
    async function fetchPortfolioDetails() {
        portfolioDetailsDiv.innerHTML = '<p>Loading portfolio...</p>';
        const data = await fetchData(`${API_BASE_URL}/portfolioDetails`);

        if (data.status === 'error') {
            portfolioDetailsDiv.innerHTML = `<p class="text-red-600">Error loading portfolio: ${data.msg}</p>`;
            return;
        }

        let html = `
            <table class="min-w-full bg-white border border-gray-200">
                <thead>
                    <tr class="bg-gray-100">
                        <th class="py-2 px-4 border-b text-left">Symbol</th>
                        <th class="py-2 px-4 border-b text-left">Quantity</th>
                        <th class="py-2 px-4 border-b text-left">Avg. Price</th>
                        <th class="py-2 px-4 border-b text-left">Current Price</th>
                        <th class="py-2 px-4 border-b text-left">P&L</th>
                        <th class="py-2 px-4 border-b text-left">Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        if (data.holdings && data.holdings.length > 0) {
            data.holdings.forEach(holding => {
                const currentPrice = data.marketPrices[holding.symbol] || holding.entryPrice; // Fallback if no live quote
                const pnl = (currentPrice - holding.entryPrice) * holding.quantity;
                const pnlClass = pnl >= 0 ? 'text-green-600' : 'text-red-600';
                html += `
                    <tr>
                        <td class="py-2 px-4 border-b">${holding.symbol}</td>
                        <td class="py-2 px-4 border-b">${holding.quantity}</td>
                        <td class="py-2 px-4 border-b">₹${holding.entryPrice.toFixed(2)}</td>
                        <td class="py-2 px-4 border-b">₹${currentPrice.toFixed(2)}</td>
                        <td class="py-2 px-4 border-b ${pnlClass}">₹${pnl.toFixed(2)}</td>
                        <td class="py-2 px-4 border-b">
                            <button class="exit-position-btn bg-red-500 hover:bg-red-600 text-white text-xs py-1 px-2 rounded-md transition duration-300" data-symbol="${holding.symbol}">Exit</button>
                        </td>
                    </tr>
                `;
            });
        } else {
            html += `<tr><td colspan="6" class="py-4 text-center text-gray-500">No holdings in portfolio.</td></tr>`;
        }
        html += `</tbody></table>`;
        portfolioDetailsDiv.innerHTML = html;

        // Add event listeners for exit buttons
        portfolioDetailsDiv.querySelectorAll('.exit-position-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const symbolToExit = e.target.dataset.symbol;
                if (confirm(`Are you sure you want to exit position for ${symbolToExit}?`)) {
                    const exitResponse = await fetchData(`${API_BASE_URL}/exitOrder?symbol=${symbolToExit}`);
                    if (exitResponse.status === 'success') {
                        alert(exitResponse.msg);
                        // Refresh all relevant sections after exit
                        fetchAccountSummary();
                        fetchPortfolioDetails();
                        fetchOrderDetails();
                    } else {
                        alert(`Failed to exit position: ${exitResponse.msg}`);
                    }
                }
            });
        });
    }
    refreshPortfolioBtn.addEventListener('click', fetchPortfolioDetails);


    // --- Order Details ---
    async function fetchOrderDetails() {
        orderDetailsDiv.innerHTML = '<p>Loading orders...</p>';
        const data = await fetchData(`${API_BASE_URL}/orderDetails`);

        if (data.status === 'error') {
            orderDetailsDiv.innerHTML = `<p class="text-red-600">Error loading orders: ${data.msg}</p>`;
            return;
        }

        let html = '<h3 class="text-xl font-medium mb-3">Buy Orders</h3>';
        if (data.buy && data.buy.length > 0) {
            html += `
                <table class="min-w-full bg-white border border-gray-200 mb-6">
                    <thead>
                        <tr class="bg-gray-100">
                            <th class="py-2 px-4 border-b text-left">Symbol</th>
                            <th class="py-2 px-4 border-b text-left">Quantity</th>
                            <th class="py-2 px-4 border-b text-left">Entry Price</th>
                            <th class="py-2 px-4 border-b text-left">Order Type</th>
                            <th class="py-2 px-4 border-b text-left">Stop Loss</th>
                            <th class="py-2 px-4 border-b text-left">Target</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            data.buy.forEach(order => {
                html += `
                    <tr>
                        <td class="py-2 px-4 border-b">${order.symbol}</td>
                        <td class="py-2 px-4 border-b">${order.quantity}</td>
                        <td class="py-2 px-4 border-b">₹${order.entryPrice.toFixed(2)}</td>
                        <td class="py-2 px-4 border-b">${order.orderType}</td>
                        <td class="py-2 px-4 border-b">₹${order.stoploss.toFixed(2)}</td>
                        <td class="py-2 px-4 border-b">₹${order.target.toFixed(2)}</td>
                    </tr>
                `;
            });
            html += `</tbody></table>`;
        } else {
            html += `<p class="text-gray-500 mb-6">No pending buy orders.</p>`;
        }

        html += '<h3 class="text-xl font-medium mb-3">Sell Orders</h3>';
        if (data.sell && data.sell.length > 0) {
            html += `
                <table class="min-w-full bg-white border border-gray-200">
                    <thead>
                        <tr class="bg-gray-100">
                            <th class="py-2 px-4 border-b text-left">Symbol</th>
                            <th class="py-2 px-4 border-b text-left">Quantity</th>
                            <th class="py-2 px-4 border-b text-left">Entry Price</th>
                            <th class="py-2 px-4 border-b text-left">Order Type</th>
                            <th class="py-2 px-4 border-b text-left">Stop Loss</th>
                            <th class="py-2 px-4 border-b text-left">Target</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            data.sell.forEach(order => {
                html += `
                    <tr>
                        <td class="py-2 px-4 border-b">${order.symbol}</td>
                        <td class="py-2 px-4 border-b">${order.quantity}</td>
                        <td class="py-2 px-4 border-b">₹${order.entryPrice.toFixed(2)}</td>
                        <td class="py-2 px-4 border-b">${order.orderType}</td>
                        <td class="py-2 px-4 border-b">₹${order.stoploss.toFixed(2)}</td>
                        <td class="py-2 px-4 border-b">₹${order.target.toFixed(2)}</td>
                    </tr>
                `;
            });
            html += `</tbody></table>`;
        } else {
            html += `<p class="text-gray-500">No pending sell orders.</p>`;
        }
        orderDetailsDiv.innerHTML = html;
    }
    refreshOrdersBtn.addEventListener('click', fetchOrderDetails);

    // --- Get Quote ---
    getQuoteForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const symbol = document.getElementById('quoteSymbol').value.toUpperCase();
        if (!symbol) {
            showMessage(quoteResultDiv, 'Please enter a symbol.', 'error');
            return;
        }
        showMessage(quoteResultDiv, 'Fetching quote...', 'info');

        const response = await fetchData(`${API_BASE_URL}/getQuote?symbol=${symbol}`);

        if (response.status === 'error') {
            showMessage(quoteResultDiv, `Error: ${response.msg}`, 'error');
        } else if (response.lp) {
            showMessage(quoteResultDiv, `Live Price for ${symbol}: ₹${parseFloat(response.lp).toFixed(2)}`, 'success');
        } else {
            showMessage(quoteResultDiv, `No live quote found for ${symbol}.`, 'info');
        }
    });

    // Initial load of all data
    fetchAccountSummary();
    fetchPortfolioDetails();
    fetchOrderDetails();
});