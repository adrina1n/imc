import math
from datamodel import Order, TradingState
from strategies.base import ProductTrader
from typing import List


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def implied_vol(market_price: float, S: float, K: float, T: float, r: float,
                tol: float = 1e-6, max_iter: int = 100) -> float:
    """Newton-Raphson IV solver."""
    sigma = 0.5
    for _ in range(max_iter):
        price = black_scholes_call(S, K, T, r, sigma)
        vega = S * math.sqrt(T) * _norm_pdf((math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T)))
        if vega < 1e-10:
            break
        sigma -= (price - market_price) / vega
        sigma = max(sigma, 1e-6)
        if abs(price - market_price) < tol:
            break
    return sigma


def _norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)


class OptionsTrader(ProductTrader):
    """
    IV scalping strategy for options products.
    Buys options when IV is below fair_iv, sells when above.
    """

    def __init__(self, symbol: str, position_limit: int, underlying_symbol: str,
                 K: float, T: float, r: float, fair_iv: float, iv_edge: float = 0.02):
        super().__init__(symbol, position_limit)
        self.underlying_symbol = underlying_symbol
        self.K = K
        self.T = T
        self.r = r
        self.fair_iv = fair_iv
        self.iv_edge = iv_edge

    def get_orders(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []

        opt_depth = state.order_depths.get(self.symbol)
        und_depth = state.order_depths.get(self.underlying_symbol)
        if opt_depth is None or und_depth is None:
            return orders

        S_mid = self.mid_price(und_depth)
        if S_mid is None:
            return orders

        opt_ask = min(opt_depth.sell_orders) if opt_depth.sell_orders else None
        opt_bid = max(opt_depth.buy_orders) if opt_depth.buy_orders else None

        pos = self.current_position(state)

        if opt_ask is not None:
            iv = implied_vol(opt_ask, S_mid, self.K, self.T, self.r)
            if iv < self.fair_iv - self.iv_edge and pos < self.position_limit:
                orders.append(Order(self.symbol, opt_ask, 1))

        if opt_bid is not None:
            iv = implied_vol(opt_bid, S_mid, self.K, self.T, self.r)
            if iv > self.fair_iv + self.iv_edge and pos > -self.position_limit:
                orders.append(Order(self.symbol, opt_bid, -1))

        return orders
