import json
import math
from typing import Any, Dict, List
from datamodel import (
    Listing, Observation, Order, OrderDepth,
    ProsperityEncoder, Symbol, Trade, TradingState
)


#  LOGGER — ne pas modifier, requis pour le visualiseur Jasper

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json([
                self.compress_state(state, ""),
                self.compress_orders(orders),
                conversions,
                "",
                "",
            ])
        )
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json([
                self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                self.compress_orders(orders),
                conversions,
                self.truncate(trader_data, max_item_length),
                self.truncate(self.logs, max_item_length),
            ])
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])
        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]
        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append([
                    trade.symbol, trade.price, trade.quantity,
                    trade.buyer, trade.seller, trade.timestamp,
                ])
        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice, observation.askPrice,
                observation.transportFees, observation.exportTariff,
                observation.importTariff, observation.sugarPrice,
                observation.sunlightIndex,
            ]
        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])
        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return value[:max_length - 3] + "..."


logger = Logger()


#  TRADER

class Trader:

    LIMITS = {
        "EMERALDS": 50,
        "TOMATOES": 50,
    }

    def __init__(self):
        # ── État par timestamp (réinitialisé à chaque run) ──
        self.orders = {}
        self.buy_orders_sent = {}
        self.sell_orders_sent = {}

        # ══════════════════════════════════════════
        #  HYPERPARAMS TOMATOES — modifie ici
        self.MA_FAST = 50        # fenêtre MA rapide
        self.MA_SLOW = 200     # fenêtre MA lente

        self.SKEW_MAX = 3        # décalage max de fair_value en ticks (intensité trend)
        self.MAX_POS_NEUTRAL  = 50   # position limit normale
        self.MAX_POS_TREND    = 20   # position limit en tendance forte
        # ══════════════════════════════════════════

        self.wall_mid_history = []   # historique wall_mid pour les MAs

    #  HELPERS GÉNÉRIQUES

    def reset_orders(self, state: TradingState):
        self.orders = {}
        self.buy_orders_sent = {}
        self.sell_orders_sent = {}

        for product in state.order_depths:
            self.orders[product] = []
            self.buy_orders_sent[product] = 0
            self.sell_orders_sent[product] = 0

    def get_position(self, state: TradingState, product: str) -> int:
        return state.position.get(product, 0)

    def get_max_buy(self, state: TradingState, product: str) -> int:
        limit = self.LIMITS[product]
        pos = self.get_position(state, product)
        return limit - pos - self.buy_orders_sent[product]

    def get_max_sell(self, state: TradingState, product: str) -> int:
        limit = self.LIMITS[product]
        pos = self.get_position(state, product)
        return pos + limit - self.sell_orders_sent[product]

    def send_buy_order(self, product: str, price: int, amount: int, msg: str = None):
        if amount <= 0:
            return
        self.orders[product].append(Order(product, int(price), amount))
        self.buy_orders_sent[product] += amount
        if msg:
            logger.print(msg)

    def send_sell_order(self, product: str, price: int, amount: int, msg: str = None):
        if amount <= 0:
            return
        self.orders[product].append(Order(product, int(price), -amount))
        self.sell_orders_sent[product] += amount
        if msg:
            logger.print(msg)

    def search_buys(self, state: TradingState, product: str, fair_value: float, depth: int = 3):
        order_depth = state.order_depths[product]
        if len(order_depth.sell_orders) == 0:
            return

        orders = list(order_depth.sell_orders.items())
        pos = self.get_position(state, product)

        for ask, amount in orders[:min(len(orders), depth)]:
            ask_volume = -amount

            take = False
            if ask < math.floor(fair_value):
                # Edge clair : toujours prendre
                take = True
            elif ask <= math.ceil(fair_value) and pos < 0:
                # Au fair value (ou entre floor/ceil) : prendre seulement si ça réduit |pos|
                take = True

            if take:
                max_buy = self.get_max_buy(state, product)
                size = min(max_buy, ask_volume)
                if size > 0:
                    self.send_buy_order(product, ask, size,
                        msg=f"TAKE BUY {size}x @ {ask}")

    def search_sells(self, state: TradingState, product: str, fair_value: float, depth: int = 3):
        order_depth = state.order_depths[product]
        if len(order_depth.buy_orders) == 0:
            return

        orders = list(order_depth.buy_orders.items())
        pos = self.get_position(state, product)

        for bid, bid_volume in orders[:min(len(orders), depth)]:
            take = False
            if bid > math.ceil(fair_value):
                # Edge clair : toujours prendre
                take = True
            elif bid >= math.floor(fair_value) and pos > 0:
                # Au fair value (ou entre floor/ceil) : prendre seulement si ça réduit |pos|
                take = True

            if take:
                max_sell = self.get_max_sell(state, product)
                size = min(max_sell, bid_volume)
                if size > 0:
                    self.send_sell_order(product, bid, size,
                        msg=f"TAKE SELL {size}x @ {bid}")

    def get_best_bid(self, state: TradingState, product: str, fair_value: float):
        order_depth = state.order_depths[product]
        if len(order_depth.buy_orders) == 0:
            return None

        for bid, _ in order_depth.buy_orders.items():
            if bid < fair_value:
                return bid

        return None

    def get_best_ask(self, state: TradingState, product: str, fair_value: float):
        order_depth = state.order_depths[product]
        if len(order_depth.sell_orders) == 0:
            return None

        for ask, _ in order_depth.sell_orders.items():
            if ask > fair_value:
                return ask

        return None

    def get_wall_mid(self, state: TradingState, product: str) -> float:
        order_depth = state.order_depths[product]

        best_wall_bid = None
        max_vol = 0
        for price, volume in order_depth.buy_orders.items():
            if volume > max_vol:
                max_vol = volume
                best_wall_bid = price

        best_wall_ask = None
        max_vol = 0
        for price, volume in order_depth.sell_orders.items():
            if abs(volume) > max_vol:
                max_vol = abs(volume)
                best_wall_ask = price

        if best_wall_bid is not None and best_wall_ask is not None:
            return (best_wall_bid + best_wall_ask) / 2

        bids = order_depth.buy_orders
        asks = order_depth.sell_orders
        if len(bids) > 0 and len(asks) > 0:
            return (max(bids.keys()) + min(asks.keys())) / 2

        return None

    #  STRATÉGIES PAR PRODUIT

    def trade_emeralds(self, state: TradingState):
        product = "EMERALDS"
        fair_value = 10000

        self.search_buys(state, product, fair_value, depth=3)
        self.search_sells(state, product, fair_value, depth=3)

        buy_price = 9996
        sell_price = 10004

        other_bid = self.get_best_bid(state, product, fair_value)
        other_ask = self.get_best_ask(state, product, fair_value)

        if other_bid is not None and other_ask is not None:
            buy_price = other_bid + 1
            sell_price = other_ask - 1

        max_buy = self.get_max_buy(state, product)
        max_sell = self.get_max_sell(state, product)
        pos = self.get_position(state, product)

        # N'achète pas plus si déjà long ET prix >= fair value (pas d'edge)
        if not (pos > 0 and buy_price >= fair_value):
            self.send_buy_order(product, buy_price, max_buy,
                msg=f"EMERALDS MM Buy {max_buy} @ {buy_price}")

        # Ne vend pas plus si déjà short ET prix <= fair value (pas d'edge)
        if not (pos < 0 and sell_price <= fair_value):
            self.send_sell_order(product, sell_price, max_sell,
                msg=f"EMERALDS MM Sell {max_sell} @ {sell_price}")

    def trade_tomatoes(self, state: TradingState):
        product = "TOMATOES"
        order_depth = state.order_depths[product]

        if len(order_depth.buy_orders) == 0 or len(order_depth.sell_orders) == 0:
            return

        # ── Fair Value : Wall Mid uniquement (EMA supprimée) ──
        fair_value = self.get_wall_mid(state, product)
        if fair_value is None:
            return

        # ── Trend detection via MA fast/slow sur wall_mid ──
        self.wall_mid_history.append(fair_value)

        ma_fast = None
        ma_slow = None
        if len(self.wall_mid_history) >= self.MA_FAST:
            ma_fast = sum(self.wall_mid_history[-self.MA_FAST:]) / self.MA_FAST
        if len(self.wall_mid_history) >= self.MA_SLOW:
            ma_slow = sum(self.wall_mid_history[-self.MA_SLOW:]) / self.MA_SLOW

        # ── Skew de fair value selon intensité du trend ──
        # trend_strength ∈ [-1, 1] : négatif = downtrend, positif = uptrend
        # on normalise par MA_slow pour rendre ça scale-invariant
        skew = 0.0
        dynamic_limit = self.MAX_POS_NEUTRAL

        if ma_fast is not None and ma_slow is not None:
            trend_strength = (ma_fast - ma_slow) / ma_slow  # ex: -0.002 = downtrend modéré
            # clamp entre -1 et 1 puis appliquer SKEW_MAX
            trend_clamped = max(-1.0, min(1.0, trend_strength * 200))
            skew = trend_clamped * self.SKEW_MAX

            # position limit dynamique : plus le trend est fort, plus on serre
            if abs(trend_clamped) > 0.3:
                dynamic_limit = self.MAX_POS_TREND
            else:
                dynamic_limit = self.MAX_POS_NEUTRAL

        # fair_value skewée : baisse en downtrend, monte en uptrend
        fair_value_skewed = fair_value + skew

        logger.print(f"TOMATOES fair={fair_value:.1f} skew={skew:.2f} fv_skewed={fair_value_skewed:.1f} limit={dynamic_limit}")

        # ── 1. Taking (sur fair value skewée) ──
        self.search_buys(state, product, fair_value_skewed, depth=3)
        self.search_sells(state, product, fair_value_skewed, depth=3)

        # ── 2. Market Making (spread autour de fair_value_skewed) ──
        buy_price = math.floor(fair_value_skewed) - 2
        sell_price = math.ceil(fair_value_skewed) + 2

        int_fair_skewed = int(math.ceil(fair_value_skewed))
        other_bid = self.get_best_bid(state, product, int_fair_skewed)
        other_ask = self.get_best_ask(state, product, int_fair_skewed)

        if other_bid is not None and other_ask is not None:
            if other_bid + 1 < fair_value_skewed:
                buy_price = other_bid + 1
            if other_ask - 1 > fair_value_skewed:
                sell_price = other_ask - 1

        # ── 3. Position-reducing avec position limit dynamique ──
        pos = self.get_position(state, product)
        max_buy  = min(self.get_max_buy(state, product),  max(0, dynamic_limit - pos))
        max_sell = min(self.get_max_sell(state, product), max(0, dynamic_limit + pos))

        # N'achète pas plus si déjà long ET prix >= fair value skewée (pas d'edge)
        if not (pos > 0 and buy_price >= math.floor(fair_value_skewed)):
            self.send_buy_order(product, buy_price, max_buy,
                msg=f"TOMATOES MM Buy {max_buy} @ {buy_price} skew={skew:.1f}")

        # Ne vend pas plus si déjà short ET prix <= fair value skewée (pas d'edge)
        if not (pos < 0 and sell_price <= math.ceil(fair_value_skewed)):
            self.send_sell_order(product, sell_price, max_sell,
                msg=f"TOMATOES MM Sell {max_sell} @ {sell_price} skew={skew:.1f}")

    #  RUN

    def run(self, state: TradingState):
        self.reset_orders(state)

        if "EMERALDS" in state.order_depths:
            self.trade_emeralds(state)

        if "TOMATOES" in state.order_depths:
            self.trade_tomatoes(state)

        trader_data = ""
        conversions = 0
        logger.flush(state, self.orders, conversions, trader_data)
        return self.orders, conversions, trader_data