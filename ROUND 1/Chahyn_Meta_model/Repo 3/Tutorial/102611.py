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
        
        # 1. Load our historical state (to remember the Tomato moving average)
        trader_state = {}
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except json.JSONDecodeError:
                pass
        
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
                fair = 10000
                
                # Take liquidity: If the market is offering free money, take it immediately
                if best_ask < fair and pos < limit:
                    buy_qty = min(limit - pos, order_depth.sell_orders[best_ask])
                    orders.append(Order(product, best_ask, buy_qty))
                    pos += buy_qty  # update local position for the next order
                
                if best_bid > fair and pos > -limit:
                    sell_qty = min(limit + pos, order_depth.buy_orders[best_bid])
                    orders.append(Order(product, best_bid, -sell_qty))
                    pos -= sell_qty
                    
                # Make liquidity: "Penny" the best bid/ask to get to the front of the queue
                # but never quote worse than our fair value margins
                buy_price  = min(best_bid + 1, fair - 1)
                sell_price = max(best_ask - 1, fair + 1)
                
                buy_qty = limit - pos
                sell_qty = limit + pos
                
                if buy_qty > 0:
                    orders.append(Order(product, buy_price, buy_qty))
                if sell_qty > 0:
                    orders.append(Order(product, sell_price, -sell_qty))
            
            elif product == "TOMATOES":
                # Mean reversion: Calculate an Exponential Moving Average (EMA)
                # Fetch the old EMA, or default to current mid if it's the first tick
                ema = trader_state.get("TOMATOES_EMA", mid)
                
                # Update EMA (alpha = 0.1 means it adapts smoothly to new prices)
                ema = 0.1 * mid + 0.9 * ema
                trader_state["TOMATOES_EMA"] = ema
                
                # Make liquidity: Instead of buying at the ask (paying the spread), 
                # place limit orders slightly away from our rolling fair value.
                buy_price = int(ema) - 2
                sell_price = int(ema) + 2
                
                buy_qty = limit - pos
                sell_qty = limit + pos
                
                if buy_qty > 0:
                    orders.append(Order(product, buy_price, buy_qty))
                if sell_qty > 0:
                    orders.append(Order(product, sell_price, -sell_qty))
        
            result[product] = orders
        
        # 2. Save state for the next tick
        trader_data = json.dumps(trader_state)
        conversions = 0
        
        return result, conversions, trader_data