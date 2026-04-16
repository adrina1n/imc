from datamodel import Order, TradingState
from strategies.base import ProductTrader
from typing import List
import math

SYMBOL = "ASH_COATED_OSMIUM"
POSITION_LIMIT = 80

# ASH is stationary around 10,000.  Wall-mid (deepest bid/ask average) gives a
# zero-lag fair value — no EMA initialisation cost and no lag from a slow alpha.
# The market spread is ~21 ticks 68% of the time, so overbidding / undercutting
# the best standing orders keeps us inside the spread without a fixed offset.

SKEW_DIV = 20       # softer than v3's 15; avoids over-correction at max pos
TAKE_EDGE = 1       # take anything ≥1 tick through FV
MAX_MAKE_VOL = 25   # cap per passive quote so we don't dump the whole limit at once


class AshMarketMaker(ProductTrader):
    """
    Resin-style market-maker for ASH_COATED_OSMIUM.

    Changes vs v3:
    1. Wall-mid FV instead of slow EMA → zero lag, no initialisation cost.
    2. Sweeps ALL mispriced levels (not just best), tracking remaining capacity
       after each fill → eliminates position-limit violations.
    3. Overbid / undercut best standing orders instead of fixed FV +/- 7.
    4. Inventory flattening at wall_mid when position > +/-5 to free capacity.
    5. MAX_MAKE_VOL cap prevents flooding one side with the entire limit.
    """

    def __init__(
        self,
        symbol: str = SYMBOL,
        position_limit: int = POSITION_LIMIT,
        skew_div: int = SKEW_DIV,
        take_edge: int = TAKE_EDGE,
        max_make_vol: int = MAX_MAKE_VOL,
    ):
        super().__init__(symbol, position_limit)
        self.skew_div = skew_div
        self.take_edge = take_edge
        self.max_make_vol = max_make_vol

    # No persistent state needed — FV is recomputed each tick from wall_mid.

    # --- core logic ---

    def get_orders(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []

        od = state.order_depths.get(self.symbol)
        if od is None:
            return orders

        buy_orders  = sorted(od.buy_orders.items(),  key=lambda x: -x[0])  # highest first
        sell_orders = sorted(od.sell_orders.items(), key=lambda x:  x[0])  # lowest first

        if not buy_orders or not sell_orders:
            return orders

        # Fair value: wall-mid (deepest resting level, zero lag)
        wall_bid = buy_orders[-1][0]
        wall_ask = sell_orders[-1][0]
        wall_mid = (wall_bid + wall_ask) / 2

        # Inventory skew: shift FV toward neutral to lean against the position
        pos      = self.current_position(state)
        skew     = pos / self.skew_div
        fv       = wall_mid - skew

        # Remaining capacity — updated after each take to prevent limit violations
        max_buy  = self.position_limit - pos
        max_sell = self.position_limit + pos

        # PHASE 1: Aggressive takes — sweep all mispriced levels
        for ask_price, ask_vol in sell_orders:
            ask_vol = abs(ask_vol)
            if ask_price <= fv - self.take_edge and max_buy > 0:
                vol = min(ask_vol, max_buy)
                orders.append(Order(self.symbol, ask_price, vol))
                max_buy -= vol
                pos += vol
            # Flatten: if we're short, buy at wall_mid to neutralise
            elif ask_price <= wall_mid and pos < -5 and max_buy > 0:
                vol = min(ask_vol, min(-pos, max_buy))
                orders.append(Order(self.symbol, ask_price, vol))
                max_buy -= vol
                pos += vol

        for bid_price, bid_vol in buy_orders:
            bid_vol = abs(bid_vol)
            if bid_price >= fv + self.take_edge and max_sell > 0:
                vol = min(bid_vol, max_sell)
                orders.append(Order(self.symbol, bid_price, -vol))
                max_sell -= vol
                pos -= vol
            # Flatten: if we're long, sell at wall_mid to neutralise
            elif bid_price >= wall_mid and pos > 5 and max_sell > 0:
                vol = min(bid_vol, min(pos, max_sell))
                orders.append(Order(self.symbol, bid_price, -vol))
                max_sell -= vol
                pos -= vol

        # PHASE 2: Passive quotes — overbid/undercut best standing orders
        bid_price = wall_bid + 1
        for bp, bv in buy_orders:
            overbid = bp + 1
            if bv > 1 and overbid < fv:
                bid_price = max(bid_price, overbid)
                break
            elif bp < fv:
                bid_price = max(bid_price, bp)
                break

        ask_price = wall_ask - 1
        for ap, av in sell_orders:
            av = abs(av)
            undercut = ap - 1
            if av > 1 and undercut > fv:
                ask_price = min(ask_price, undercut)
                break
            elif ap > fv:
                ask_price = min(ask_price, ap)
                break

        # Ensure quotes don't cross
        bid_price = int(bid_price)
        ask_price = int(ask_price)
        if bid_price >= ask_price:
            bid_price = int(math.floor(fv)) - 1
            ask_price = int(math.ceil(fv))  + 1

        buy_vol  = min(max_buy,  self.max_make_vol)
        sell_vol = min(max_sell, self.max_make_vol)

        if buy_vol > 0:
            orders.append(Order(self.symbol, bid_price,  buy_vol))
        if sell_vol > 0:
            orders.append(Order(self.symbol, ask_price, -sell_vol))

        return orders
