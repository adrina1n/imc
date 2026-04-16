"""
IMC Prosperity Data Model
=========================
This is the official datamodel.py used in IMC Prosperity competitions.

DO NOT modify this file when submitting to the competition — IMC provides
it automatically on their servers. Include it in your local project so
your IDE and backtester work correctly.

This version is compatible with Prosperity 3 / Prosperity 4.
Source: Alpha Animals (P3, 9th place) — slightly extended with defaults
        to make local testing easier (Observation accepts optional args, etc.)

Classes:
    Listing             - A tradable product on the exchange
    ConversionObservation - External market data for cross-exchange products
    Observation         - Container for all external observations
    Order               - A single buy or sell instruction
    OrderDepth          - The full order book for one product
    Trade               - A completed trade between two participants
    TradingState        - Everything your Trader receives each tick
    ProsperityEncoder   - JSON encoder for serializing the above classes
"""

import json
from typing import Dict, List, Optional
from json import JSONEncoder

# ── Type aliases ──────────────────────────────────────────────────────────────
Time = int              # timestamp in milliseconds
Symbol = str            # product symbol, e.g. "RAINFOREST_RESIN"
Product = str           # same as Symbol in most contexts
Position = int          # units held: positive = long, negative = short
UserId = str            # trader identifier, e.g. "Olivia" or "SUBMISSION"
ObservationValue = int  # external data point value


# ── Listing ───────────────────────────────────────────────────────────────────
class Listing:
    """
    Describes a tradable product available on the exchange.

    Attributes:
        symbol      The product ticker, e.g. "RAINFOREST_RESIN"
        product     The underlying product name (same as symbol in practice)
        denomination The currency products are priced in ("SEASHELLS")
    """

    def __init__(self, symbol: Symbol, product: Product, denomination: Product):
        self.symbol = symbol
        self.product = product
        self.denomination = denomination

    def __repr__(self) -> str:
        return f"Listing({self.symbol})"


# ── ConversionObservation ─────────────────────────────────────────────────────
class ConversionObservation:
    """
    External market data for products that trade on a second exchange
    (e.g. MAGNIFICENT_MACARONS in Prosperity 3).

    Your bot can request conversions between the two markets.
    The effective import cost  = askPrice  + transportFees + importTariff
    The effective export revenue = bidPrice - transportFees - exportTariff

    Attributes:
        bidPrice        External market best bid
        askPrice        External market best ask
        transportFees   Fixed fee per conversion (both directions)
        exportTariff    Additional fee when exporting (selling externally)
        importTariff    Additional fee when importing (buying externally)
        sugarPrice      Supplementary observation (Prosperity 3)
        sunlightIndex   Supplementary observation (Prosperity 3)
    """

    def __init__(
        self,
        bidPrice: float,
        askPrice: float,
        transportFees: float,
        exportTariff: float,
        importTariff: float,
        sugarPrice: float = 0.0,
        sunlightIndex: float = 0.0,
    ):
        self.bidPrice = bidPrice
        self.askPrice = askPrice
        self.transportFees = transportFees
        self.exportTariff = exportTariff
        self.importTariff = importTariff
        self.sugarPrice = sugarPrice
        self.sunlightIndex = sunlightIndex

    def import_cost(self) -> float:
        """Total cost to import one unit (buy externally, sell internally)."""
        return self.askPrice + self.transportFees + self.importTariff

    def export_revenue(self) -> float:
        """Net revenue to export one unit (buy internally, sell externally)."""
        return self.bidPrice - self.transportFees - self.exportTariff

    def __repr__(self) -> str:
        return (
            f"ConversionObservation(bid={self.bidPrice}, ask={self.askPrice}, "
            f"transport={self.transportFees})"
        )


# ── Observation ───────────────────────────────────────────────────────────────
class Observation:
    """
    Container for all external observations delivered each tick.

    Attributes:
        plainValueObservations  {product: int} for simple external prices
        conversionObservations  {product: ConversionObservation} for cross-exchange products
    """

    def __init__(
        self,
        plainValueObservations: Optional[Dict[Product, ObservationValue]] = None,
        conversionObservations: Optional[Dict[Product, ConversionObservation]] = None,
    ):
        self.plainValueObservations = plainValueObservations or {}
        self.conversionObservations = conversionObservations or {}

    def __repr__(self) -> str:
        return (
            f"Observation(plain={list(self.plainValueObservations.keys())}, "
            f"conversion={list(self.conversionObservations.keys())})"
        )


# ── Order ─────────────────────────────────────────────────────────────────────
class Order:
    """
    A single trading instruction returned by your Trader.

    Your run() method returns {symbol: [Order, Order, ...]} dicts.

    Attributes:
        symbol      Which product to trade
        price       Limit price (integer SeaShells)
        quantity    +N to buy N units, -N to sell N units
    """

    def __init__(self, symbol: Symbol, price: int, quantity: int) -> None:
        self.symbol = symbol
        self.price = price
        self.quantity = quantity

    def __str__(self) -> str:
        side = "BUY" if self.quantity > 0 else "SELL"
        return f"Order({self.symbol} {side} {abs(self.quantity)} @ {self.price})"

    def __repr__(self) -> str:
        return self.__str__()


# ── OrderDepth ────────────────────────────────────────────────────────────────
class OrderDepth:
    """
    The full order book for one product at one timestamp.

    buy_orders:  {price: +volume}  — resting bids (positive quantities)
    sell_orders: {price: -volume}  — resting asks (negative quantities)

    Example:
        buy_orders  = {9998: 10, 9997: 25}  means 10 units wanted @ 9998
        sell_orders = {10002: -8, 10003: -15} means 8 units offered @ 10002

    Usage:
        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())
        mid      = (best_bid + best_ask) / 2
    """

    def __init__(
        self,
        buy_orders: Optional[Dict[int, int]] = None,
        sell_orders: Optional[Dict[int, int]] = None,
    ):
        self.buy_orders: Dict[int, int] = buy_orders if buy_orders is not None else {}
        self.sell_orders: Dict[int, int] = sell_orders if sell_orders is not None else {}

    def best_bid(self) -> Optional[int]:
        """Highest bid price, or None if no bids."""
        return max(self.buy_orders.keys()) if self.buy_orders else None

    def best_ask(self) -> Optional[int]:
        """Lowest ask price, or None if no asks."""
        return min(self.sell_orders.keys()) if self.sell_orders else None

    def mid_price(self) -> Optional[float]:
        """Midpoint between best bid and best ask, or None."""
        b, a = self.best_bid(), self.best_ask()
        return (b + a) / 2.0 if b is not None and a is not None else None

    def __repr__(self) -> str:
        return f"OrderDepth(bids={len(self.buy_orders)}, asks={len(self.sell_orders)})"


# ── Trade ─────────────────────────────────────────────────────────────────────
class Trade:
    """
    A completed trade between two participants.

    Appears in state.own_trades (your fills) and state.market_trades (all trades).

    Attributes:
        symbol      Product that was traded
        price       Execution price
        quantity    Units traded (always positive)
        buyer       UserId of the buyer (your ID = "SUBMISSION")
        seller      UserId of the seller
        timestamp   When the trade occurred (milliseconds)
    """

    def __init__(
        self,
        symbol: Symbol,
        price: int,
        quantity: int,
        buyer: Optional[UserId] = None,
        seller: Optional[UserId] = None,
        timestamp: int = 0,
    ) -> None:
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.buyer = buyer
        self.seller = seller
        self.timestamp = timestamp

    def __str__(self) -> str:
        return (
            f"Trade({self.symbol} {self.quantity}@{self.price} "
            f"{self.buyer}>>{self.seller} t={self.timestamp})"
        )

    def __repr__(self) -> str:
        return self.__str__()


# ── TradingState ──────────────────────────────────────────────────────────────
class TradingState:
    """
    Everything your Trader.run() receives each tick.

    The exchange calls Trader.run(state) every ~100ms.
    Your method must return: (Dict[Symbol, List[Order]], int, str)
                              orders              conversions traderData

    Attributes:
        traderData      JSON string you returned last tick (your memory)
        timestamp       Current time in milliseconds
        listings        {symbol: Listing} — available products
        order_depths    {symbol: OrderDepth} — current order books
        own_trades      {symbol: [Trade]} — your fills from last tick
        market_trades   {symbol: [Trade]} — all trades last tick (incl. others)
        position        {symbol: int} — your current holdings
        observations    Observation — external market data

    Limits (Prosperity 4):
        traderData: ~100KB max (crashes if exceeded)
        print output: ~3750 chars per tick (silently truncated if exceeded)
        position limits enforced per product (orders exceeding limit are rejected)
    """

    def __init__(
        self,
        traderData: str,
        timestamp: Time,
        listings: Dict[Symbol, Listing],
        order_depths: Dict[Symbol, "OrderDepth"],
        own_trades: Dict[Symbol, List[Trade]],
        market_trades: Dict[Symbol, List[Trade]],
        position: Dict[Product, Position],
        observations: Observation,
    ):
        self.traderData = traderData
        self.timestamp = timestamp
        self.listings = listings
        self.order_depths = order_depths
        self.own_trades = own_trades
        self.market_trades = market_trades
        self.position = position
        self.observations = observations

    def toJSON(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True)

    def __repr__(self) -> str:
        products = list(self.order_depths.keys())
        return f"TradingState(t={self.timestamp}, products={products})"


# ── ProsperityEncoder ─────────────────────────────────────────────────────────
class ProsperityEncoder(JSONEncoder):
    """
    JSON encoder that handles all IMC datamodel objects.
    Used by the Logger class to serialize state for the visualizer.

    Usage:
        json.dumps(my_object, cls=ProsperityEncoder, separators=(',', ':'))
    """

    def default(self, o):
        return o.__dict__


# ── Convenience constants ─────────────────────────────────────────────────────
# Position limits by product (Prosperity 3 / estimated Prosperity 4)
POSITION_LIMITS: Dict[str, int] = {
    "RAINFOREST_RESIN": 50,
    "KELP": 50,
    "SQUID_INK": 50,
    "CROISSANTS": 250,
    "JAMS": 350,
    "DJEMBES": 60,
    "PICNIC_BASKET1": 60,
    "PICNIC_BASKET2": 100,
    "MAGNIFICENT_MACARONS": 75,
    "VOLCANIC_ROCK": 400,
    "VOLCANIC_ROCK_VOUCHER_9500": 200,
    "VOLCANIC_ROCK_VOUCHER_9750": 200,
    "VOLCANIC_ROCK_VOUCHER_10000": 200,
    "VOLCANIC_ROCK_VOUCHER_10250": 200,
    "VOLCANIC_ROCK_VOUCHER_10500": 200,
}

# Basket compositions (Prosperity 3)
BASKET_COMPOSITIONS: Dict[str, Dict[str, int]] = {
    "PICNIC_BASKET1": {"CROISSANTS": 6, "JAMS": 3, "DJEMBES": 1},
    "PICNIC_BASKET2": {"CROISSANTS": 4, "JAMS": 2},
}
