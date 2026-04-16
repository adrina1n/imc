from datamodel import Order, TradingState
from strategies.base import ProductTrader
from typing import List


class CommodityTrader(ProductTrader):
    """
    Conversion arbitrage for commodity products with a conversion mechanism.
    Exploits price gaps between the exchange price and conversion value.
    """

    def __init__(self, symbol: str, position_limit: int, conversion_cost: float, threshold: float = 1.0):
        """
        Args:
            symbol: Tradeable symbol on the exchange.
            position_limit: Max position.
            conversion_cost: Total cost (fees + transport) per unit converted.
            threshold: Min profit above conversion_cost to trigger conversion.
        """
        super().__init__(symbol, position_limit)
        self.conversion_cost = conversion_cost
        self.threshold = threshold

    def get_orders(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []

        obs = state.observations.conversionObservations.get(self.symbol)
        order_depth = state.order_depths.get(self.symbol)
        if obs is None or order_depth is None:
            return orders

        # obs attributes depend on the round — adapt accordingly
        # e.g. obs.bidPrice, obs.askPrice, obs.transportFees, obs.importTariff
        conversion_ask = getattr(obs, "askPrice", None)
        conversion_bid = getattr(obs, "bidPrice", None)

        exch_bid = self.best_bid(order_depth)
        exch_ask = self.best_ask(order_depth)

        pos = self.current_position(state)

        if conversion_ask is not None and exch_bid is not None:
            profit = exch_bid - conversion_ask - self.conversion_cost
            if profit > self.threshold and pos > -self.position_limit:
                orders.append(Order(self.symbol, exch_bid, -1))

        if conversion_bid is not None and exch_ask is not None:
            profit = conversion_bid - exch_ask - self.conversion_cost
            if profit > self.threshold and pos < self.position_limit:
                orders.append(Order(self.symbol, exch_ask, 1))

        return orders
