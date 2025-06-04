import csv
from NorenRestApiPy.NorenApi import  NorenApi
import uuid
import os
import pickle


class ShoonyaApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(self, host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')        
        global api
        api = self


class Order:
    def __init__(self, symbol: str, quantity: int, orderSide: str, token: int, entryPrice: float=0.0, orderType='market', stoploss: float = None, target: float = None):
        self.symbol = symbol
        self.quantity = quantity
        self.entryPrice = entryPrice
        self.orderSide = orderSide
        self.orderType = orderType
        self.stoploss = stoploss
        self.target = target
        self.token = token
        self.avgPrice = entryPrice
        print("Order object created")

    def __add__(self, obj):
        if self.symbol == obj.symbol:
            self.quantity += obj.quantity
            if self.quantity == 0:
                self.avgPrice = 0.0
            else:
                self.avgPrice = (self.avgPrice * (self.quantity - obj.quantity) + obj.entryPrice * obj.quantity) / (self.quantity)
            self.stoploss = obj.stoploss
            self.orderSide = 'sell' if self.quantity < 0 else "buy"
            self.target = obj.target
            return self
        else:
            return {"error": "Cannot add different stocks"}

class OrderBook:
    def __init__(self):
        self.buyOrders = []
        self.sellOrders = []

        if os.path.exists("orderbook.pkl"):
            try:
                with open("orderbook.pkl", "rb") as f:
                    saved_orderbook = pickle.load(f)
                    self.buyOrders = saved_orderbook.buyOrders
                    self.sellOrders = saved_orderbook.sellOrders
                print("OrderBook loaded from orderbook.pkl")
            except Exception as e:
                print(f"Failed to load orderbook.pkl: {e}")
        else:
            print("No existing orderbook.pkl found. Starting fresh.")

    def save(self):
        try:
            with open("orderbook.pkl", "wb") as f:
                pickle.dump(self, f)
            print("OrderBook saved to orderbook.pkl")
        except Exception as e:
            print(f"Failed to save OrderBook: {e}")

    def addOrder(self, order):
        try:
            if order.orderSide == "buy":
                self.buyOrders.append(order)
                print("placed order")
            elif order.orderSide == "sell":
                self.sellOrders.append(order)
                print("placed order")
        except Exception as e:
            print(f"Error in addOrder in utils {e}")
    # def modifyQuantity(self, newQuantity: int, orderId: str):
    #     for order in self.buyOrders + self.sellOrders:
    #         if order.id == orderId:
    #             order.quantity = newQuantity
    #             self.save()
    #             return vars(order)
    #     return {"error": "Order not found"}

    # def modifyEntryPrice(self, newPrice: int, orderId: str):
    #     for order in self.buyOrders + self.sellOrders:
    #         if order.id == orderId:
    #             order.entryPrice = newPrice
    #             self.save()
    #             return vars(order)
    #     return {"error": "Order not found"}

    # def modifyTarget(self, newTarget: int, orderId: str):
    #     for order in self.buyOrders + self.sellOrders:
    #         if order.id == orderId:
    #             order.target = newTarget
    #             self.save()
    #             return vars(order)
    #     return {"error": "Order not found"}

    # def modifyStoploss(self, newStoploss: int, orderId: str):
    #     for order in self.buyOrders + self.sellOrders:
    #         if order.id == orderId:
    #             order.stoploss = newStoploss
    #             self.save()
    #             return vars(order)
    #     return {"error": "Order not found"}

    def executeOrder(self, priceDict: dict, portfolio_object):
        executed_buys = []
        executed_sells = []
        response = []
        try:
            # print(priceDict)
            for buy in self.buyOrders:
                # print(f"{buy.symbol}\t{buy.quantity}\t{buy.entryPrice}\t{priceDict[buy.token]}")
                if buy.orderType == 'market' and buy.token in priceDict:
                    buy.entryPrice = buy.avgPrice = priceDict[buy.token]
                    response += portfolio_object.addPosition(buy)
                    print(f"Bought {buy.quantity} of {buy.symbol} at {buy.avgPrice}")
                    executed_buys.append(buy)
                elif buy.orderType == 'limit' and buy.token in priceDict:
                    if priceDict[buy.token] <= buy.entryPrice:
                        buy.entryPrice = buy.avgPrice = priceDict[buy.token]
                        response += portfolio_object.addPosition(buy)
                        print(f"Bought {buy.quantity} of {buy.symbol} at {buy.avgPrice}")
                        executed_buys.append(buy)
            for order in executed_buys:
                self.buyOrders.remove(order)
            

            for sell in self.sellOrders:
                # print(f"{sell.symbol}\t{sell.quantity}\t{sell.entryPrice}\t{priceDict[sell.token]}")
                if sell.orderType == 'market' and sell.token in priceDict:
                    sell.entryPrice = sell.avgPrice = priceDict[sell.token]
                    print("Inside sell execute")
                    response += portfolio_object.addPosition(sell)
                    print(f"Sold {sell.quantity} of {sell.symbol} at {sell.avgPrice}")
                    executed_sells.append(sell)
                elif sell.orderType == 'limit' and sell.token in priceDict:
                    if priceDict[sell.token] >= sell.entryPrice:
                        sell.entryPrice = sell.avgPrice = priceDict[sell.token]
                        response += portfolio_object.addPosition(sell)
                        print(f"Sold {sell.quantity} of {sell.symbol} at {sell.avgPrice}")
                        executed_sells.append(sell)
            for order in executed_sells:
                self.sellOrders.remove(order)

        except Exception as e:
            print(f"Error: in executeOrder {e}")


class Portfolio:
    def __init__(self):
        self.holdings = {}
        self.initialCapital = 1000000
        self.availableCapital = self.initialCapital

        if os.path.exists("portfolio.pkl"):
            try:
                with open("portfolio.pkl", "rb") as f:
                    saved_portfolio = pickle.load(f)
                    self.holdings = saved_portfolio.holdings
                    self.initialCapital = saved_portfolio.initialCapital
                    self.availableCapital = saved_portfolio.availableCapital
                print("Portfolio loaded from portfolio.pkl")
            except Exception as e:
                print(f"Failed to load portfolio.pkl: {e}")
        else:
            print("No existing portfolio.pkl found. Starting fresh.")

    def save(self):
        try:
            with open("portfolio.pkl", "wb") as f:
                pickle.dump(self, f)
            print("Portfolio saved to portfolio.pkl")
        except Exception as e:
            print(f"Failed to save Portfolio: {e}")

    def addPosition(self, position):
        cost = abs(position.quantity * position.entryPrice)
        if self.availableCapital >=cost:
            if position.quantity > 0:
                self.availableCapital -= position.quantity * position.entryPrice
            elif position.quantity < 0:
                self.availableCapital -= position.quantity * position.entryPrice

            if position.symbol in self.holdings:
                self.holdings[position.symbol] += position
                if self.holdings[position.symbol].quantity == 0:
                    del self.holdings[position.symbol]
            else:
                self.holdings[position.symbol] = position
                
            self.save()
            return position.__dict__
        print("Insuffiecint money!")
        return "Insuffiecint money!"
    
    def showPosition(self, symbol):
        return self.holdings.get(symbol)

    def exitPosition(self, symbol: str):
        pass

    def showHoldings(self):
        return self.holdings

def generateDict(path="NSE_symbols.csv"):
    symbolDict = {}
    with open(path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            symbolDict[row[3].upper()] = row[1]
    return symbolDict
