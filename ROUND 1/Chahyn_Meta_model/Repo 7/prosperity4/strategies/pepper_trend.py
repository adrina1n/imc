from datamodel import Order, TradingState
from strategies.base import ProductTrader
from typing import List

SYMBOL = "INTARIAN_PEPPER_ROOT"
POSITION_LIMIT = 80

# Pepper trended +3,000 over 3 days — non-stationary, purely directional.
# Strategy: build max long as efficiently as possible, then hold.
#
# Hybrid entry splits the load:
#   - First AGGRESSIVE_TARGET units: take best ask immediately (need exposure fast)
#   - Remaining units: limit bids at bb+1 -> saves ~10 ticks per passive fill
#     vs slamming the ask, recovering 300-400 PnL and reducing initial drawdown.
#
# Once full: only post an impossibly wide ask (ba+20) — almost never fills,
# preserving the long position to ride the full trend.

AGGRESSIVE_TARGET = 80   # take aggressively up to this many units
MAX_PASSIVE_VOL   = 20   # max volume per passive bid layer


class PepperTrendTrader(ProductTrader):
    """
    Hybrid directional loader for INTARIAN_PEPPER_ROOT.

    Changes vs v3:
    1. Two-phase entry: aggressive take for first 40 units, then limit bids
       at bb+1 for remaining 40 -> saves ~10 ticks/unit on passive fills.
    2. Second passive layer at best_bid mops up remaining capacity.
    3. Wide ask (ba+20) once full — avoids accidentally resetting position
       and restarting the entry cost.
    """

    def __init__(
        self,
        symbol: str = SYMBOL,
        position_limit: int = POSITION_LIMIT,
        aggressive_target: int = AGGRESSIVE_TARGET,
        max_passive_vol: int = MAX_PASSIVE_VOL,
    ):
        super().__init__(symbol, position_limit)
        self.aggressive_target = aggressive_target
        self.max_passive_vol = max_passive_vol

    # No persistent state needed — logic is purely positional.

    # --- core logic ---

    def get_orders(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []

        od = state.order_depths.get(self.symbol)
        if od is None:
            return orders

        buy_orders  = sorted(od.buy_orders.items(),  key=lambda x: -x[0])
        sell_orders = sorted(od.sell_orders.items(), key=lambda x:  x[0])

        pos       = self.current_position(state)
        remaining = self.position_limit - pos

        # Already at max long — post a wide ask to avoid accidental unwind
        if remaining <= 0:
            if sell_orders:
                widest_ask = sell_orders[-1][0]
                orders.append(Order(self.symbol, widest_ask + 20, -1))
            return orders

        if not sell_orders and not buy_orders:
            return orders

        best_ask     = sell_orders[0][0] if sell_orders else None
        best_ask_vol = abs(sell_orders[0][1]) if sell_orders else 0
        best_bid     = buy_orders[0][0] if buy_orders else None

        # PHASE 1: Aggressive — take best ask until AGGRESSIVE_TARGET units held
        if pos < self.aggressive_target and best_ask is not None:
            aggressive_remaining = self.aggressive_target - pos
            take_vol = min(best_ask_vol, aggressive_remaining, remaining)
            if take_vol > 0:
                orders.append(Order(self.symbol, best_ask, take_vol))
                remaining -= take_vol
                pos += take_vol

        # PHASE 2: Passive layer at bb+1 (saves ~10 ticks vs slamming the ask)
        if remaining > 0 and best_bid is not None:
            passive_vol = min(remaining, self.max_passive_vol)
            orders.append(Order(self.symbol, best_bid + 1, passive_vol))
            remaining -= passive_vol

        # PHASE 3: Second layer at best_bid — mop up leftover capacity
        if remaining > 0 and best_bid is not None:
            orders.append(Order(self.symbol, best_bid, remaining))

        return orders
