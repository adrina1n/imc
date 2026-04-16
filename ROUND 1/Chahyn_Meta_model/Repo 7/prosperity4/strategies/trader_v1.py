from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json
import math

class Trader:
    def __init__(self):
        # Set your position limits here. (Update these if Round 1 rules specify different limits)
        self.POSITION_LIMITS = {
            "ASH_COATED_OSMIUM": 20,
            "INTARIAN_PEPPER_ROOT": 20
        }
        
        # Configuration for ASH_COATED_OSMIUM (Stationary)
        self.ASH_FAIR_VALUE = 10000
        
        # Configuration for INTARIAN_PEPPER_ROOT (Trending)
        self.PEPPER_EMA_ALPHA = 0.2  # Smoothing factor (higher = reacts to price changes faster)

    def run(self, state: TradingState):
        """
        Only method required. It takes all inputs and returns a tuple of (orders, conversions, trader_data).
        """
        # Dictionary to hold the orders for each product
        result = {}
        
        # We start by parsing the persistent state from the previous timestamp (used for the EMA)
        trader_data = {}
        if state.traderData:
            try:
                trader_data = json.loads(state.traderData)
            except Exception as e:
                pass # If it's the first timestamp or corrupted, start fresh
                
        # ---------------------------------------------------------
        # 1. Process ASH_COATED_OSMIUM (The "Anchor" Strategy)
        # ---------------------------------------------------------
        ash_product = "ASH_COATED_OSMIUM"
        if ash_product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[ash_product]
            orders: List[Order] = []
            
            # Get current position and calculate limits
            current_position = state.position.get(ash_product, 0)
            limit = self.POSITION_LIMITS[ash_product]
            
            # --- MARKET TAKING (Clear "Free Money") ---
            # Buy if someone is selling below fair value
            if len(order_depth.sell_orders) != 0:
                best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                if best_ask < self.ASH_FAIR_VALUE:
                    buy_amount = min(-best_ask_amount, limit - current_position)
                    if buy_amount > 0:
                        orders.append(Order(ash_product, best_ask, buy_amount))
                        current_position += buy_amount

            # Sell if someone is buying above fair value
            if len(order_depth.buy_orders) != 0:
                best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                if best_bid > self.ASH_FAIR_VALUE:
                    sell_amount = max(-best_bid_amount, -limit - current_position) # sell amounts are negative
                    if sell_amount < 0:
                        orders.append(Order(ash_product, best_bid, sell_amount))
                        current_position += sell_amount

            # --- MARKET MAKING (Capture the spread) ---
            # How much room do we have left to trade?
            max_buy = limit - current_position
            max_sell = -limit - current_position

            # Shift quotes based on inventory to prevent hitting the limit
            position_skew = int(current_position / 4)
            
            my_bid = self.ASH_FAIR_VALUE - 4 - position_skew
            my_ask = self.ASH_FAIR_VALUE + 4 - position_skew

            # Place the passive orders if we have room
            if max_buy > 0:
                orders.append(Order(ash_product, my_bid, max_buy))
            if max_sell < 0:
                orders.append(Order(ash_product, my_ask, max_sell))

            result[ash_product] = orders


        # ---------------------------------------------------------
        # 2. Process INTARIAN_PEPPER_ROOT (The "Escalator" + OBI Protection)
        # ---------------------------------------------------------
        pepper_product = "INTARIAN_PEPPER_ROOT"
        if pepper_product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[pepper_product]
            orders: List[Order] = []
            
            current_position = state.position.get(pepper_product, 0)
            limit = self.POSITION_LIMITS[pepper_product]
            
            if len(order_depth.sell_orders) > 0 and len(order_depth.buy_orders) > 0:
                best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                mid_price = (best_ask + best_bid) / 2.0
                
                # --- ORDER BOOK IMBALANCE (OBI) CALCULATION ---
                # Note: ask amounts are negative in the datamodel, so we use abs()
                total_volume = best_bid_amount + abs(best_ask_amount)
                obi = best_bid_amount / total_volume if total_volume > 0 else 0.5
            else:
                mid_price = None

            if mid_price is not None:
                # Update Exponential Moving Average (EMA)
                prev_ema = trader_data.get("pepper_ema", mid_price)
                current_ema = (self.PEPPER_EMA_ALPHA * mid_price) + ((1 - self.PEPPER_EMA_ALPHA) * prev_ema)
                trader_data["pepper_ema"] = current_ema
                
                my_bid = math.floor(current_ema - 3)
                my_ask = math.ceil(current_ema + 6) 
                
                max_buy = limit - current_position
                max_sell = -limit - current_position
                
                # --- OBI PROTECTION LOGIC ---
                if obi > 0.8:
                    # Massive buying pressure: Price is about to spike!
                    # Cancel our market-making asks so we don't get run over.
                    max_sell = 0 
                elif obi < 0.2:
                    # Massive selling pressure: Price is about to dump!
                    # Cancel our market-making bids so we don't catch a falling knife.
                    max_buy = 0
                
                # Opportunistic Market Taking: Aggressive buy if price dips significantly below the EMA
                # (We still allow this even if OBI is low, because a massive dip below EMA is highly profitable)
                if best_ask < current_ema - 2:
                    buy_amount = min(abs(best_ask_amount), max_buy)
                    if buy_amount > 0:
                        orders.append(Order(pepper_product, best_ask, buy_amount))
                        max_buy -= buy_amount
                        current_position += buy_amount
                        max_sell = -limit - current_position # Re-adjust sell limit after taking
                
                # Place Market Making Orders around the moving average (filtered by OBI)
                if max_buy > 0:
                    orders.append(Order(pepper_product, my_bid, max_buy))
                if max_sell < 0: # Note: max_sell is negative, so this checks if we still want to sell
                    orders.append(Order(pepper_product, my_ask, max_sell))
                    
            result[pepper_product] = orders

        # ---------------------------------------------------------
        # 3. Finalize and Return
        # ---------------------------------------------------------
        
        # Serialize the trader data state so it can be passed into the next timestamp
        next_trader_data = json.dumps(trader_data)
        conversions = 0 # No conversions in Round 1 usually
        
        return result, conversions, next_trader_data