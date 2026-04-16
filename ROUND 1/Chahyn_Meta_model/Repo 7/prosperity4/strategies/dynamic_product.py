from datamodel import Order, TradingState
from strategies.base import ProductTrader
from typing import List
from collections import deque


class DynamicProductTrader(ProductTrader):
    """
    Market-making strategy for random-walk / non-stationary products.
    Estimates fair value from a rolling mid-price EMA.
    """

    def __init__(self, symbol: str, position_limit: int, ema_alpha: float = 0.2, half_spread: int = 2):
        super().__init__(symbol, position_limit)
        self.ema_alpha = ema_alpha
        self.half_spread = half_spread
        self.ema: float | None = None

    def get_orders(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []
        order_depth = state.order_depths.get(self.symbol)
        if order_depth is None:
            return orders

        mid = self.mid_price(order_depth)
        if mid is None:
            return orders

        if self.ema is None:
            self.ema = mid
        else:
            self.ema = self.ema_alpha * mid + (1 - self.ema_alpha) * self.ema

        pos = self.current_position(state)
        bid_price = round(self.ema - self.half_spread)
        ask_price = round(self.ema + self.half_spread)

        buy_capacity = self.position_limit - pos
        sell_capacity = self.position_limit + pos

        if buy_capacity > 0:
            orders.append(Order(self.symbol, bid_price, buy_capacity))
        if sell_capacity > 0:
            orders.append(Order(self.symbol, ask_price, -sell_capacity))

        return orders
