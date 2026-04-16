from datamodel import Order, TradingState
from strategies.base import ProductTrader
from typing import List


class StaticProductTrader(ProductTrader):
    """
    Market-making strategy for stationary / mean-reverting products.
    Quotes around a fair value with a configurable spread.
    """

    def __init__(self, symbol: str, position_limit: int, fair_value: float, half_spread: int = 1):
        super().__init__(symbol, position_limit)
        self.fair_value = fair_value
        self.half_spread = half_spread

    def get_orders(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []
        pos = self.current_position(state)

        bid_price = round(self.fair_value - self.half_spread)
        ask_price = round(self.fair_value + self.half_spread)

        buy_capacity = self.position_limit - pos
        sell_capacity = self.position_limit + pos

        if buy_capacity > 0:
            orders.append(Order(self.symbol, bid_price, buy_capacity))
        if sell_capacity > 0:
            orders.append(Order(self.symbol, ask_price, -sell_capacity))

        return orders
