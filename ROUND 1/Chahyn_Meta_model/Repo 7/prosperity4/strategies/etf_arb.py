from datamodel import Order, TradingState
from strategies.base import ProductTrader
from typing import List


class ETFArbTrader:
    """
    Spread / ETF arbitrage between a basket and its constituents.
    Trades the ETF vs. a weighted combination of component symbols.
    """

    def __init__(self, etf_symbol: str, components: dict[str, float], position_limit: int, threshold: float = 2.0):
        """
        Args:
            etf_symbol: Symbol for the ETF / basket product.
            components: {symbol: weight} mapping for constituents.
            position_limit: Max position on each leg.
            threshold: Min spread (in price units) to trigger a trade.
        """
        self.etf_symbol = etf_symbol
        self.components = components
        self.position_limit = position_limit
        self.threshold = threshold

    def get_orders(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []

        etf_depth = state.order_depths.get(self.etf_symbol)
        if etf_depth is None:
            return orders

        # Compute synthetic NAV from component mid prices
        nav = 0.0
        for symbol, weight in self.components.items():
            depth = state.order_depths.get(symbol)
            if depth is None:
                return orders
            bid = max(depth.buy_orders) if depth.buy_orders else None
            ask = min(depth.sell_orders) if depth.sell_orders else None
            if bid is None or ask is None:
                return orders
            nav += weight * (bid + ask) / 2

        etf_bid = max(etf_depth.buy_orders) if etf_depth.buy_orders else None
        etf_ask = min(etf_depth.sell_orders) if etf_depth.sell_orders else None

        if etf_bid is not None and etf_bid - nav > self.threshold:
            # ETF overpriced — sell ETF, buy components
            orders.append(Order(self.etf_symbol, etf_bid, -1))

        if etf_ask is not None and nav - etf_ask > self.threshold:
            # ETF underpriced — buy ETF, sell components
            orders.append(Order(self.etf_symbol, etf_ask, 1))

        return orders
