from datamodel import OrderDepth, TradingState, Order
import json

####### SYMBOLS #######

STATIC_SYMBOL  = 'EMERALDS'   # stable fair value — market make around wall mid
DYNAMIC_SYMBOL = 'TOMATOES'   # mean-reverting / trending — passive market make for now

POS_LIMITS = {
    STATIC_SYMBOL:  20,
    DYNAMIC_SYMBOL: 20,
}

####### CONFIG #######

STATIC_EDGE = 1   # min ticks of edge required to take on EMERALDS


class ProductTrader:
    """Base class with order-book utilities and order helpers."""

    def __init__(self, name, state, prints, new_trader_data, product_group=None):
        self.orders = []
        self.name   = name
        self.state  = state
        self.prints = prints
        self.new_trader_data = new_trader_data
        self.product_group   = name if product_group is None else product_group

        self.last_traderData = self._load_traderData()

        self.position_limit    = POS_LIMITS.get(self.name, 0)
        self.initial_position  = self.state.position.get(self.name, 0)
        self.expected_position = self.initial_position

        self.mkt_buy_orders, self.mkt_sell_orders = self._parse_order_depth()
        self.bid_wall, self.wall_mid, self.ask_wall = self._get_walls()
        self.best_bid, self.best_ask = self._get_best_bid_ask()

        self.max_allowed_buy_volume  = self.position_limit - self.initial_position
        self.max_allowed_sell_volume = self.position_limit + self.initial_position

        self.total_mkt_buy_volume  = sum(self.mkt_buy_orders.values())
        self.total_mkt_sell_volume = sum(self.mkt_sell_orders.values())

    # ── internals ──────────────────────────────────────────────────────────────

    def _load_traderData(self):
        try:
            if self.state.traderData:
                return json.loads(self.state.traderData)
        except:
            self.log('ERROR', 'traderData parse failed')
        return {}

    def _parse_order_depth(self):
        buy_orders = sell_orders = {}
        try:
            od: OrderDepth = self.state.order_depths[self.name]
            buy_orders  = {p: abs(v) for p, v in sorted(od.buy_orders.items(),  reverse=True)}
            sell_orders = {p: abs(v) for p, v in sorted(od.sell_orders.items())}
        except:
            pass
        return buy_orders, sell_orders

    def _get_walls(self):
        bid_wall = ask_wall = wall_mid = None
        try: bid_wall = min(self.mkt_buy_orders)
        except: pass
        try: ask_wall = max(self.mkt_sell_orders)
        except: pass
        try: wall_mid = (bid_wall + ask_wall) / 2
        except: pass
        return bid_wall, wall_mid, ask_wall

    def _get_best_bid_ask(self):
        best_bid = best_ask = None
        try: best_bid = max(self.mkt_buy_orders)
        except: pass
        try: best_ask = min(self.mkt_sell_orders)
        except: pass
        return best_bid, best_ask

    # ── order helpers ──────────────────────────────────────────────────────────

    def bid(self, price, volume):
        vol = min(abs(int(volume)), self.max_allowed_buy_volume)
        if vol <= 0: return
        self.orders.append(Order(self.name, int(price), vol))
        self.log('BUY',  {'p': int(price), 'v': vol}, product_group='ORDERS')
        self.max_allowed_buy_volume -= vol

    def ask(self, price, volume):
        vol = min(abs(int(volume)), self.max_allowed_sell_volume)
        if vol <= 0: return
        self.orders.append(Order(self.name, int(price), -vol))
        self.log('SELL', {'p': int(price), 'v': vol}, product_group='ORDERS')
        self.max_allowed_sell_volume -= vol

    # ── logging ────────────────────────────────────────────────────────────────

    def log(self, kind, message, product_group=None):
        pg = product_group or self.product_group
        if pg == 'ORDERS':
            self.prints.setdefault(pg, []).append({kind: message})
        else:
            self.prints.setdefault(pg, {})[kind] = message

    def get_orders(self):
        return {}


class StaticTrader(ProductTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(STATIC_SYMBOL, state, prints, new_trader_data)

    def get_orders(self):
        if self.wall_mid is None:
            return {self.name: self.orders}

        # 1. Take mispriced orders
        for sp, sv in self.mkt_sell_orders.items():
            if sp <= self.wall_mid - STATIC_EDGE:
                self.bid(sp, sv)
            elif sp <= self.wall_mid and self.initial_position < 0:
                self.bid(sp, min(sv, abs(self.initial_position)))

        for bp, bv in self.mkt_buy_orders.items():
            if bp >= self.wall_mid + STATIC_EDGE:
                self.ask(bp, bv)
            elif bp >= self.wall_mid and self.initial_position > 0:
                self.ask(bp, min(bv, self.initial_position))

        # 2. Market make: overbid best bid below mid, underbid best ask above mid
        bid_price = int(self.bid_wall + 1)
        ask_price = int(self.ask_wall - 1)

        for bp, bv in self.mkt_buy_orders.items():
            candidate = bp + 1
            if bv > 1 and candidate < self.wall_mid:
                bid_price = max(bid_price, candidate)
                break
            elif bp < self.wall_mid:
                bid_price = max(bid_price, bp)
                break

        for sp, sv in self.mkt_sell_orders.items():
            candidate = sp - 1
            if sv > 1 and candidate > self.wall_mid:
                ask_price = min(ask_price, candidate)
                break
            elif sp > self.wall_mid:
                ask_price = min(ask_price, sp)
                break

        self.bid(bid_price, self.max_allowed_buy_volume)
        self.ask(ask_price, self.max_allowed_sell_volume)

        return {self.name: self.orders}


class DynamicTrader(ProductTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(DYNAMIC_SYMBOL, state, prints, new_trader_data)

    def get_orders(self):
        if self.wall_mid is None:
            return {self.name: self.orders}

        # 1. Take mispriced orders
        for sp, sv in self.mkt_sell_orders.items():
            if sp <= self.wall_mid - STATIC_EDGE:
                self.bid(sp, sv)
            elif sp <= self.wall_mid and self.initial_position < 0:
                self.bid(sp, min(sv, abs(self.initial_position)))

        for bp, bv in self.mkt_buy_orders.items():
            if bp >= self.wall_mid + STATIC_EDGE:
                self.ask(bp, bv)
            elif bp >= self.wall_mid and self.initial_position > 0:
                self.ask(bp, min(bv, self.initial_position))

        # 2. Market make: overbid best bid below mid, underbid best ask above mid
        bid_price = int(self.bid_wall + 1)
        ask_price = int(self.ask_wall - 1)

        for bp, bv in self.mkt_buy_orders.items():
            candidate = bp + 1
            if bv > 1 and candidate < self.wall_mid:
                bid_price = max(bid_price, candidate)
                break
            elif bp < self.wall_mid:
                bid_price = max(bid_price, bp)
                break

        for sp, sv in self.mkt_sell_orders.items():
            candidate = sp - 1
            if sv > 1 and candidate > self.wall_mid:
                ask_price = min(ask_price, candidate)
                break
            elif sp > self.wall_mid:
                ask_price = min(ask_price, sp)
                break

        self.bid(bid_price, self.max_allowed_buy_volume)
        self.ask(ask_price, self.max_allowed_sell_volume)

        return {self.name: self.orders}


# ── Main entry point ───────────────────────────────────────────────────────────

class Trader:

    def run(self, state: TradingState):
        new_trader_data = {}
        prints = {
            'GENERAL': {
                'TIMESTAMP': state.timestamp,
                'POSITIONS': state.position,
            }
        }

        product_traders = {
            STATIC_SYMBOL:  StaticTrader,
            DYNAMIC_SYMBOL: DynamicTrader,
        }

        result, conversions = {}, 0

        for symbol, TraderClass in product_traders.items():
            if symbol in state.order_depths:
                try:
                    trader = TraderClass(state, prints, new_trader_data)
                    result.update(trader.get_orders())
                except Exception as e:
                    prints.setdefault('ERRORS', {})[symbol] = str(e)

        try:
            final_trader_data = json.dumps(new_trader_data)
        except:
            final_trader_data = ''

        try:
            print(json.dumps(prints))
        except:
            pass

        return result, conversions, final_trader_data