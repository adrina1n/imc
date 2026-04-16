from datamodel import Order, TradingState
from strategies.base import ProductTrader
from typing import List

SYMBOL = "INTARIAN_PEPPER_ROOT"
POSITION_LIMIT = 50


class PepperMeanReversionTrader(ProductTrader):
    """
    Mean-reversion strategy for INTARIAN_PEPPER_ROOT.

    Logic:
    - Maintains a rolling EMA of the wall mid-price.
    - Goes max-long  when mid < EMA - threshold  (price below fair value).
    - Goes max-short when mid > EMA + threshold  (price above fair value).
    - Flattens toward zero when mid is within the band (no edge).

    State (ema) is persisted across ticks via traderData JSON so that
    the EMA survives re-instantiation on every tick.
    """

    def __init__(
        self,
        symbol: str = SYMBOL,
        position_limit: int = POSITION_LIMIT,
        ema_alpha: float = 0.15,
        threshold: float = 3.0,
    ):
        super().__init__(symbol, position_limit)
        self.ema_alpha = ema_alpha
        self.threshold = threshold
        self.ema: float | None = None

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def load_state(self, data: dict) -> None:
        self.ema = data.get(self.symbol + "_ema")

    def dump_state(self, data: dict) -> None:
        data[self.symbol + "_ema"] = self.ema

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def get_orders(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []

        order_depth = state.order_depths.get(self.symbol)
        if order_depth is None:
            return orders

        mid = self.mid_price(order_depth)
        if mid is None:
            return orders

        # Update EMA — warm-start on first tick
        if self.ema is None:
            self.ema = mid
        else:
            self.ema = self.ema_alpha * mid + (1 - self.ema_alpha) * self.ema

        pos = self.current_position(state)
        best_ask = self.best_ask(order_depth)
        best_bid = self.best_bid(order_depth)

        deviation = mid - self.ema

        if deviation < -self.threshold:
            # Price is cheap relative to EMA — go long
            if best_ask is not None:
                buy_qty = self.position_limit - pos   # fill up to limit
                if buy_qty > 0:
                    orders.append(Order(self.symbol, best_ask, buy_qty))

        elif deviation > self.threshold:
            # Price is rich relative to EMA — go short
            if best_bid is not None:
                sell_qty = self.position_limit + pos  # sell down to -limit
                if sell_qty > 0:
                    orders.append(Order(self.symbol, best_bid, -sell_qty))

        else:
            # Inside the band — exit any open position
            if pos > 0 and best_bid is not None:
                orders.append(Order(self.symbol, best_bid, -pos))
            elif pos < 0 and best_ask is not None:
                orders.append(Order(self.symbol, best_ask, -pos))

        return orders
