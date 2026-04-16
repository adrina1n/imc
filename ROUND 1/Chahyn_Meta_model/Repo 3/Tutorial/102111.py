from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:
    
    POSITION_LIMITS = {
        "TOMATOES": 50,
        "EMERALDS": 10,
    }
    
    def run(self, state: TradingState):
        result = {}
        
        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            limit = self.POSITION_LIMITS.get(product, 20)
            pos = state.position.get(product, 0)
            
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue
            
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            mid = (best_bid + best_ask) / 2
            
            if product == "EMERALDS":
                # Market making: quote tight around mid
                # Fair value is ~10000, spread is wide so we undercut
                fair = 10000
                buy_price  = fair - 1   # bid at 9999
                sell_price = fair + 1   # ask at 10001
                
                buy_qty  = min(5, limit - pos)
                sell_qty = min(5, limit + pos)
                
                if buy_qty > 0:
                    orders.append(Order(product, buy_price, buy_qty))
                if sell_qty > 0:
                    orders.append(Order(product, sell_price, -sell_qty))
            
            elif product == "TOMATOES":
                # Mean reversion: fade moves away from rolling fair value
                # Simple version: use mid price as signal
                fair = 5000  # rough baseline from data
                
                if mid < fair - 5 and pos < limit:
                    # Price is below fair, buy
                    qty = min(5, limit - pos)
                    orders.append(Order(product, best_ask, qty))  # market buy
                
                elif mid > fair + 5 and pos > -limit:
                    # Price is above fair, sell
                    qty = min(5, limit + pos)
                    orders.append(Order(product, best_bid, -qty))  # market sell
            
            result[product] = orders
        
        # traderData persists state between ticks (JSON string)
        trader_data = json.dumps({})
        
        # conversions: for currency conversion products (none here)
        conversions = 0
        
        return result, conversions, trader_data