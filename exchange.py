from flask import Flask, request, render_template, jsonify
from commons.utils import ShoonyaApiPy, Portfolio, Order, OrderBook, generateDict
import pyotp
from config import *
import time
import os # Import os module

"""
To Do:
0: Fix short sell
1: Add multiple exchange support
2: Add documentation
"""
socket_opened = False
SYMBOLDICT = {}
api = ShoonyaApiPy()
totp = pyotp.TOTP(totpCode)
portfolio = Portfolio()
orderBook = OrderBook()

# Ensure these paths are correct relative to your app.py
# If your app.py is in the root, and assets/NSE_symbols.csv is in root
# Then the path should be correct. Otherwise, adjust as needed.
symbolToToken = generateDict(os.path.join(os.path.dirname(__file__), 'assets', 'NSE_symbols.csv'))
tokenToSymbol = {value:key for key, value in symbolToToken.items()}


def event_handler_order_update(message):
    print("order event: " + str(message))


def event_handler_quote_update(message):
    global SYMBOLDICT
    global orderBook
    global portfolio

    # Ensure message contains 'lp' and 'tk' and 'lp' is a float
    if 'lp' in message and 'tk' in message:
        try:
            message['lp'] = float(message['lp'])
            key = message['tk']

            if key in SYMBOLDICT:
                if isinstance(SYMBOLDICT[key], dict):
                    SYMBOLDICT[key] = message['lp'] # Update the price within the dict
                else: # if it's just a price, convert to dict
                     SYMBOLDICT[key] = message['lp']
            else:
                SYMBOLDICT[key] = message['lp'] # Store as a dict for consistency
            
            # print(f"Updated SYMBOLDICT: {SYMBOLDICT.get(key, 'N/A')}")
            orderBook.executeOrder(SYMBOLDICT, portfolio)
        except ValueError as e:
            print(f"Error converting 'lp' to float: {e} for message: {message}")
        except Exception as e:
            print(f"Error in event_handler_quote_update: {e}")
    else:
        pass
        # print(f"Invalid quote update message (missing 'lp' or 'tk'): {message}")


def open_callback():
    global socket_opened
    global portfolio
    socket_opened = True
    try:
        stocks = ['NSE|'+value.token for key, value in portfolio.holdings.items()]
        for stock in stocks:
            # print(f"subscribed {stock}")
            api.subscribe(stock)
        print('Websocket connection started!!')
    except Exception as e:
        print(f"Error in open_callback: {e}")
    

def close_callback():
    global socket_opened
    socket_opened = False
    print('Websocket connection is closed!!')


def create_exchange_server():
    # Configure Flask to serve static files and templates
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    ret = api.login(userid=uid, password=pwd, twoFA=totp.now(), vendor_code=vc, api_secret=app_key, imei=imei)
    # Check if login was successful before starting websocket
    if ret and ret.get('stat') == 'Ok': # Assuming 'stat' is the key for status
        print(f"Logged in using {ret['uname']} account!!")
        # Start websocket only if login is successful
        wb = api.start_websocket(subscribe_callback=event_handler_quote_update, socket_open_callback=open_callback, socket_close_callback=close_callback)
    else:
        print("Login failed!!")
        # You might want to handle this more robustly, e.g., exit or return an error Flask app
        if ret:
            print(f"Login error message: {ret.get('emsg', 'Unknown error')}")
        else:
            print("Login response was None.")


    @app.route("/")
    def home():
        return render_template("index.html") # Render the HTML file

    @app.route("/getQuote") #works
    def get_Quote():
        exchange = request.args.get('exchange', 'NSE').upper()
        symbol = request.args.get('symbol', '').upper() # Get symbol, ensure it's uppercase
        token = symbolToToken.get(symbol, None) # Use None as default

        if token is None:
            return jsonify({'status':'error', 'msg':f'No such stock found: {symbol}'})

        # Ensure that the token received from symbolToToken is used to get the quote
        response = api.get_quotes(exchange, token)
        # Assuming get_quotes returns a dict with 'lp' for last price
        if response and response.get('stat') == 'Ok':
            return jsonify({'status': 'success', 'lp': response.get('lp')})
        else:
            return jsonify({'status': 'error', 'msg': response.get('emsg', 'Failed to get quote')})

    @app.route("/getOrder")# works
    def getOrder():
        global socket_opened
        global SYMBOLDICT # This is updated by websocket, so it should be available

        try:
            exchange = request.args.get('exchange', 'NSE').upper()
            orderSide = request.args.get('type', 'buy').lower()
            symbol = request.args.get('symbol', '').upper()
            entryPrice = float(request.args.get('entryPrice', "0.0"))
            quantity = int(request.args.get('quantity', "0"))
            # Correct quantity for sell orders if it's coming as positive
            if orderSide == 'sell' and quantity > 0:
                quantity = -quantity

            stoploss = float(request.args.get('stoploss', "0"))
            orderType = request.args.get('orderType', 'market').lower() # Default to market if not provided
            target = float(request.args.get('target', "0"))

            token = symbolToToken.get(symbol, None)
            if token is None:
                return jsonify({'status':'error', 'msg':f'No such stock found: {symbol}'})

            order = Order(symbol, quantity, orderSide, token, entryPrice, orderType, stoploss, target)
            print(f"Adding order: {order.__dict__}")

            # Subscribe only if not already subscribed. Shoonya API handles duplicate subscriptions.
            api.subscribe(f"{exchange}|{token}")
            print(f"Subscribed to {exchange}|{token}")

            orderBook.addOrder(order)
            orderBook.executeOrder(SYMBOLDICT, portfolio) # Execute immediately with current prices if available

            print("Order processing initiated.")
            return jsonify({'status':'success', 'symbol': symbol, 'quantity': quantity, 'orderSide': orderSide, 'orderType': orderType})

        except ValueError as ve:
            print(f"ValueError in getOrder: {ve}")
            return jsonify({'status':'error', 'msg':f'Invalid input: {ve}'})
        except KeyError as ke:
            print(f"KeyError in getOrder (likely symbol not found): {ke}")
            return jsonify({'status':'error', 'msg':f'Symbol not found or invalid: {symbol}'})
        except Exception as e:
            print(f"Unexpected error in getOrder: {e}")
            return jsonify({'status':'error', 'msg':str(e)})


    @app.route("/exitOrder") #Works
    def exitOrder():
        global SYMBOLDICT
        global portfolio
        symbol = request.args.get("symbol", "").upper()
        exchange = request.args.get("exchange", "NSE").upper()

        position = portfolio.showPosition(symbol)
        if not position:
            return jsonify({'status':'error', 'msg':f"{symbol} not in portfolio"})

        # To exit a position, the quantity should be the opposite of the current holding.
        # If you hold 100, you sell 100 (quantity -100). If you short -50, you buy 50 (quantity 50).
        quantity_to_exit = -position.quantity # This will make it positive for short positions, negative for long
        orderSide = 'sell' if quantity_to_exit < 0 else 'buy'
        orderType = 'market'
        token = position.token

        try:
            exitOrder = Order(symbol, quantity_to_exit, orderSide, token, 0.0, orderType) # Entry price, SL, Target are irrelevant for market exit
            api.subscribe(f"{exchange}|{token}") # Subscribe to ensure live updates for execution
            orderBook.addOrder(exitOrder)
            orderBook.executeOrder(SYMBOLDICT, portfolio)
            api.unsubscribe(f"{exchange}|{token}")
            print(f"Exit order initiated for {symbol}: {exitOrder.__dict__}")
            return jsonify({'status':'success', 'msg':f'Successfully placed exit order for {symbol}'})
        except Exception as e:
            print(f"Error exiting order: {e}")
            return jsonify({'status':'error', 'msg':str(e)})


    @app.route("/portfolioDetails")
    def portfolioDetails():
        global portfolio
        global SYMBOLDICT # We need this for current prices

        # Initialize holdings as empty list if portfolio.holdings is None or empty
        holdings_list = []
        if portfolio.holdings:
            # Iterate through the dictionary values (Position objects) and convert to dict
            for symbol_key, position_obj in portfolio.holdings.items():
                holdings_list.append(position_obj.__dict__)

        marketPrice = {}
        # Ensure SYMBOLDICT values are dicts with 'lp' before accessing
        for token, price_info in SYMBOLDICT.items():
            if isinstance(price_info, dict) and 'lp' in price_info:
                symbol = tokenToSymbol.get(token)
                if symbol:
                    marketPrice[symbol] = price_info['lp'] # Get the actual last price
            elif isinstance(price_info, (float, int)): # Fallback for old direct price storage
                symbol = tokenToSymbol.get(token)
                if symbol:
                    marketPrice[symbol] = price_info


        return jsonify({'initialCapital':portfolio.initialCapital, 'holdings':holdings_list, 'marketPrices':marketPrice })


    @app.route("/orderDetails")
    def orderDetails():
        global orderBook

        buy_orders_list = [i.__dict__ for i in orderBook.buyOrders]
        sell_orders_list = [i.__dict__ for i in orderBook.sellOrders]
        return jsonify({'buy':buy_orders_list, 'sell':sell_orders_list})

    return app

if __name__=="__main__":
    # Ensure your Shoonya API key, userid, etc., are correctly configured in config.py
    # and that commons/utils.py contains the ShoonyaApiPy, Portfolio, Order, OrderBook, generateDict classes.
    app = create_exchange_server()
    app.run(debug=True) # debug=True is good for development, but set to False for production