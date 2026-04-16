"""
Round 1 Trader — INTARIAN_PEPPER_ROOT (IPR) & ASH_COATED_OSMIUM (ACO)
=======================================================================

Analysis findings:
  IPR: perfectly linear trend, slope=0.001/ts, +1000/day.
       FV start is estimated dynamically on the first tick (snapped to nearest 1000).
       B&H massively dominates MM because daily drift (~1000 ticks) >> spread income.
  ACO: stationary at mu=10000, AR(1) bounce ACF lag-1≈-0.50, no trend.
       Microprice and mean-reversion aware MM are the right tools.

Switchable strategies:
  IPR_STRATEGY:
    "bh"        — buy-and-hold: only buy asks below FV, never sell
    "take"      — two-sided taking: sell bids>FV first (free room), then buy asks<FV
    "make_sym"  — take + symmetric passive MM (spread condition gated)
    "make_asym" — take + asymmetric MM with drift-based higher ask floor

  ACO_STRATEGY:
    "make"      — pure passive MM at best_bid+1/best_ask-1, inventory skewed
    "make_rev"  — mean-reversion aware MM centered on fv_make (microprice→mu blend)
    "take"      — pure taking using conservative fv_take threshold
    "hybrid"    — taking (fv_take) first, then making (fv_make)
    "naive"     — FV = live mid; take vs mid; make at best_bid+1 / best_ask-1

Run:
    cd backtester-repo
    prosperity3bt ../round1/trader.py 0 --data data --print --no-out
"""

from typing import Any, Dict, List, Optional
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
import json

####### LOGGER #######

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([self.compress_state(state, ""), self.compress_orders(orders), conversions, "", ""]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [state.timestamp, trader_data, self.compress_listings(state.listings),
                self.compress_order_depths(state.order_depths), self.compress_trades(state.own_trades),
                self.compress_trades(state.market_trades), state.position, self.compress_observations(state.observations)]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
                for arr in trades.values() for t in arr]

    def compress_observations(self, observations: Observation) -> list[Any]:
        conv = {p: [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex]
                for p, o in observations.conversionObservations.items()}
        return [observations.plainValueObservations, conv]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."
            if len(json.dumps(candidate)) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return out

logger = Logger()

# ── Strategy switches (change these to experiment) ───────────────────────────
IPR_STRATEGY = "make_asym"
ACO_STRATEGY = "hybrid"

# ── Shared ───────────────────────────────────────────────────────────────────
POSITION_LIMIT = 80

# ── IPR parameters ────────────────────────────────────────────────────────────
# FV increases at 0.001 per timestamp unit; timestamps step by 100 → +0.1 per tick
IPR_SLOPE = 0.001
# FV start is unknown at competition time; estimated dynamically on the first tick
# by observing mid price and subtracting timestamp*slope, then snapping to nearest 1000.
# (Historical analysis confirmed it is always a multiple of 1000.)
IPR_FV_START_FALLBACK = 13000  # safety fallback if first tick has no book

# Drift premium for asymmetric makes: ask floor = FV + IPR_ASK_DRIFT_PREMIUM.
# Rationale: selling gives up future drift (0.1 ticks/step), so we demand
# at least this many ticks above FV before parting with a unit.
IPR_ASK_DRIFT_PREMIUM = 2

IPR_MAKE_VOL = 10   # max units per passive quote leg
# Last timestamp in a trading day. Used to compute end-of-day FV as the buy gate:
# we buy any ask below fv_eod (≈ fv_start + 1000), since IPR is always worth more
# by close. Current FV ≈ market price, so current-FV gate would block all buying.
IPR_MAX_TS = 999900

# ── ACO parameters ────────────────────────────────────────────────────────────
ACO_MU    = 10000.0   # long-run fair value
ACO_SIGMA = 2.55      # rolling std of mid price (from notebook analysis)

# fv_make = ALPHA*microprice + (1-ALPHA)*mu
# Reduced from 0.70 → 0.40 to tone down mean-reversion reactivity.
# Lower ALPHA → quotes are more anchored to mu, less chasing of short-term moves.
ACO_ALPHA = 0.40

# fv_take = mu + RHO*(fv_make - mu)
# Restored to 0.50: take on moderate deviations from mu (0.30 was too conservative).
ACO_RHO   = 0.50

ACO_MAKE_VOL = 20    # max units per passive quote leg (increased from 10 — wide spread supports higher volume)
ACO_SKEW_K   = 0.10  # inventory-skew coefficient
ACO_TARGET   = 0     # neutral inventory target


class Trader:

    def __init__(self):
        # type: () -> None
        # IPR FV start is estimated from the first observed mid price.
        self._ipr_fv_start = None  # type: Optional[float]

    # ──────────────────────────────────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────────────────────────────────

    def run(self, state: TradingState):
        # type: (TradingState) -> tuple
        result = {}  # type: Dict[str, List[Order]]

        for product in state.order_depths:
            od       = state.order_depths[product]
            position = state.position.get(product, 0)
            orders   = []  # type: List[Order]

            if product == "INTARIAN_PEPPER_ROOT":
                self._trade_ipr(od, position, state.timestamp, orders)
            elif product == "ASH_COATED_OSMIUM":
                self._trade_aco(od, position, orders)

            result[product] = orders

        conversions = 0
        trader_data = ""
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data

    # ══════════════════════════════════════════════════════════════════════════
    # IPR — INTARIAN_PEPPER_ROOT
    # ══════════════════════════════════════════════════════════════════════════

    def _estimate_ipr_fv_start(self, od, timestamp):
        # type: (OrderDepth, int) -> None
        """
        Estimate IPR_FV_START from the first observed mid price.
        raw_start = mid - timestamp * slope → should be close to a multiple of 1000.
        Snap to nearest 1000 to get the exact start (historical R²≈1 confirms integer
        multiples of 1000 are always the true intercept).
        """
        if not od.buy_orders or not od.sell_orders:
            self._ipr_fv_start = float(IPR_FV_START_FALLBACK)
            return
        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        mid      = (best_bid + best_ask) / 2.0
        raw_start = mid - timestamp * IPR_SLOPE
        # Snap to nearest multiple of 1000
        self._ipr_fv_start = float(round(raw_start / 1000) * 1000)

    def _trade_ipr(self, od, position, timestamp, orders):
        # type: (OrderDepth, int, int, List[Order]) -> None

        # Estimate FV start once on the first tick
        if self._ipr_fv_start is None:
            self._estimate_ipr_fv_start(od, timestamp)

        fv     = self._ipr_fv_start + timestamp * IPR_SLOPE          # type: float
        fv_eod = self._ipr_fv_start + IPR_MAX_TS * IPR_SLOPE         # end-of-day FV

        if IPR_STRATEGY == "bh":
            # Strategy 1: buy-only B&H
            self._ipr_take_buyside(od, fv_eod, position, orders)

        elif IPR_STRATEGY == "take":
            # Strategy 2: two-sided taking
            self._ipr_take(od, fv, fv_eod, position, orders)

        elif IPR_STRATEGY == "make_sym":
            # Strategy 3a: take first, then symmetric passive MM
            pos2 = self._ipr_take(od, fv, fv_eod, position, orders)
            self._ipr_make(od, fv, pos2, orders, asymmetric=False)

        elif IPR_STRATEGY == "make_asym":
            # Strategy 3b: take first, then drift-biased asymmetric MM
            pos2 = self._ipr_take(od, fv, fv_eod, position, orders)
            self._ipr_make(od, fv, pos2, orders, asymmetric=True)

    # ── IPR Layer 1: taking ───────────────────────────────────────────────────

    def _ipr_take_buyside(self, od, fv_eod, position, orders):
        # type: (OrderDepth, float, int, List[Order]) -> int
        """
        Strategy 1 (B&H): accumulate long at any ask below end-of-day FV. Never sell.
        fv_eod = fv_start + 999900 * slope ≈ fv_start + 1000.
        Current market trades ~1000 below fv_eod all day, so this gate always passes —
        it is equivalent to always buying but makes the FV comparison explicit.
        """
        for ask in sorted(od.sell_orders.keys()):
            if ask >= fv_eod:
                break
            can_buy = POSITION_LIMIT - position
            if can_buy <= 0:
                break
            qty = min(-od.sell_orders[ask], can_buy)
            orders.append(Order("INTARIAN_PEPPER_ROOT", ask, qty))
            position += qty
        return position

    def _ipr_take(self, od, fv, fv_eod, position, orders):
        # type: (OrderDepth, float, float, int, List[Order]) -> int
        """
        Position-aware two-sided taking.
          fv     = current-tick FV (used as sell gate: bid > fv means genuine overpricing)
          fv_eod = end-of-day FV  (used as buy  gate: ask < fv_eod always passes since
                                   market trades ~1000 below close value all day)

        Not at limit → buy asks < fv_eod first, then sell bids > fv.
        At limit     → sell bids > fv first (free room), then buy asks < fv_eod.
        """
        if position < POSITION_LIMIT:
            # Fill up aggressively — buy anything below end-of-day FV
            for ask in sorted(od.sell_orders.keys()):
                if ask >= fv_eod:
                    break
                can_buy = POSITION_LIMIT - position
                if can_buy <= 0:
                    break
                qty = min(-od.sell_orders[ask], can_buy)
                orders.append(Order("INTARIAN_PEPPER_ROOT", ask, qty))
                position += qty
            # Then take any bids genuinely above current FV
            for bid in sorted(od.buy_orders.keys(), reverse=True):
                if bid <= fv:
                    break
                can_sell = POSITION_LIMIT + position
                if can_sell <= 0:
                    break
                qty = min(od.buy_orders[bid], can_sell)
                orders.append(Order("INTARIAN_PEPPER_ROOT", bid, -qty))
                position -= qty
        else:
            # At limit: sell mispriced bids first to free room
            for bid in sorted(od.buy_orders.keys(), reverse=True):
                if bid <= fv:
                    break
                can_sell = POSITION_LIMIT + position
                if can_sell <= 0:
                    break
                qty = min(od.buy_orders[bid], can_sell)
                orders.append(Order("INTARIAN_PEPPER_ROOT", bid, -qty))
                position -= qty
            # Immediately refill below end-of-day FV
            for ask in sorted(od.sell_orders.keys()):
                if ask >= fv_eod:
                    break
                can_buy = POSITION_LIMIT - position
                if can_buy <= 0:
                    break
                qty = min(-od.sell_orders[ask], can_buy)
                orders.append(Order("INTARIAN_PEPPER_ROOT", ask, qty))
                position += qty

        return position

    # ── IPR Layer 2: making ───────────────────────────────────────────────────

    def _ipr_make(self, od, fv, position, orders, asymmetric=False):
        # type: (OrderDepth, float, int, List[Order], bool) -> None
        """
        Passive MM for IPR. Only post if the profit from each fill exceeds the
        drift earned by holding for one timestamp step.

        Profitability condition per leg:
          - Bid: edge = FV - bid_price. Must exceed drift_per_step (0.1).
                 Since bid_price ≤ FV-1, edge ≥ 1 > 0.1. Always satisfied.
          - Ask: edge = ask_price - FV. Must exceed drift_per_step (0.1).
                 Since ask_price ≥ FV+1, edge ≥ 1 > 0.1. Always satisfied.
        So the binding constraint is simply: must have room inside the live spread
        (best_ask - best_bid > 1) to quote with edge on both sides.

        No inventory skew: holding IPR long is always good (drift dominates),
        so we do not penalise being long or push quotes toward any target.

        asymmetric=False (make_sym):
          Ask floor at FV+1 — the minimum passive ask. WARNING: selling at FV+1
          captures 1 tick of edge but surrenders ALL remaining drift on that unit
          (which compounds over the rest of the day). This is almost always a bad
          trade. make_sym exists for completeness but make_asym is preferred.

        asymmetric=True (make_asym):
          Raise ask floor to FV + IPR_ASK_DRIFT_PREMIUM (default 2 ticks).
          We only sell if someone bids at least 2 ticks above FV, which partially
          compensates for giving up the drift earned by holding that unit.
          The bid side is unchanged — buying is always welcome.
        """
        if not od.buy_orders or not od.sell_orders:
            return

        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())

        # Require live spread > 1 so there is room to post inside with edge
        if best_ask - best_bid <= 1:
            return

        fv_int = int(fv)

        # Base quotes: queue-jump by 1 tick, clamped to FV ± 1
        bid_price = min(best_bid + 1, fv_int - 1)
        ask_price = max(best_ask - 1, fv_int + 1)

        if asymmetric:
            # Drift-based asymmetry: raise ask floor so we don't sell drift cheaply
            ask_price = max(ask_price, fv_int + IPR_ASK_DRIFT_PREMIUM)

        if bid_price >= ask_price:
            return

        buy_room  = POSITION_LIMIT - position
        sell_room = POSITION_LIMIT + position

        if buy_room > 0:
            orders.append(Order("INTARIAN_PEPPER_ROOT", bid_price,
                                min(IPR_MAKE_VOL, buy_room)))
        if sell_room > 0:
            orders.append(Order("INTARIAN_PEPPER_ROOT", ask_price,
                                -min(IPR_MAKE_VOL, sell_room)))

    # ══════════════════════════════════════════════════════════════════════════
    # ACO — ASH_COATED_OSMIUM
    # ══════════════════════════════════════════════════════════════════════════

    def _aco_fair_values(self, od):
        # type: (OrderDepth) -> tuple
        """
        Compute the two ACO fair value estimates.

        microprice:
          Volume-weighted mid price. More bid volume → price should drift up →
          microprice > simple mid. Captures short-term order flow pressure.
          Formula: (ask * bid_vol + bid * ask_vol) / (bid_vol + ask_vol)

        fv_make = ALPHA * microprice + (1-ALPHA) * mu
          Shrinks microprice toward the long-run mean.
          ACO_ALPHA=0.40 (reduced from 0.70): quotes are more anchored to mu,
          less reactive to transient microprice moves.

        fv_take = mu + RHO * (fv_make - mu)
          Conservative version for taking. ACO_RHO=0.30 (reduced from 0.50):
          fv_take is only 30% of the way from mu toward fv_make, requiring
          a stronger true deviation before we aggressively cross the spread.

        Returns (fv_make, fv_take) or (None, None) if book is empty.
        """
        if not od.buy_orders or not od.sell_orders:
            return None, None

        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        bid_vol  = float(od.buy_orders[best_bid])      # positive
        ask_vol  = float(-od.sell_orders[best_ask])    # make positive

        # Microprice: biased toward ask when bid_vol > ask_vol (buying pressure)
        total_vol  = bid_vol + ask_vol
        microprice = (best_ask * bid_vol + best_bid * ask_vol) / total_vol

        # fv_make: blend toward mu for stability (less reactive with ALPHA=0.40)
        fv_make = ACO_ALPHA * microprice + (1.0 - ACO_ALPHA) * ACO_MU

        # fv_take: diluted — requires stronger deviation before taking (RHO=0.30)
        fv_take = ACO_MU + ACO_RHO * (fv_make - ACO_MU)

        return fv_make, fv_take

    def _trade_aco(self, od, position, orders):
        # type: (OrderDepth, int, List[Order]) -> None
        fv_make, fv_take = self._aco_fair_values(od)
        if fv_make is None:
            return

        if ACO_STRATEGY == "make":
            # Strategy 1: simple passive MM, no FV model
            self._aco_make_pure(od, position, orders)

        elif ACO_STRATEGY == "make_rev":
            # Strategy 2: mean-reversion aware MM (quotes centered on fv_make)
            self._aco_make_rev(od, fv_make, position, orders)

        elif ACO_STRATEGY == "take":
            # Strategy 3: pure taking using fv_take
            self._aco_take(od, fv_take, position, orders)

        elif ACO_STRATEGY == "hybrid":
            # Strategy 4: take first (fv_take), then make (fv_make)
            pos2 = self._aco_take(od, fv_take, position, orders)
            self._aco_make_rev(od, fv_make, pos2, orders)

        elif ACO_STRATEGY == "naive":
            # Strategy 5: baseline — FV = live mid; take vs mid; make 1 tick inside spread
            self._aco_naive(od, position, orders)

    # ── ACO Strategy 1: pure passive MM ──────────────────────────────────────

    def _aco_make_pure(self, od, position, orders):
        # type: (OrderDepth, int, List[Order]) -> None
        """
        Quote 1 tick inside best bid/ask, clamped to mu±1.
        Inventory skew shifts both quotes by -skew_k*(pos-target):
          long → skew negative → quotes shift down → sell more eagerly.
          short → skew positive → quotes shift up → buy more eagerly.

        Clamp order: base price first, then add skew, then re-clamp to spread.
        Skewing before the spread clamp can push a bid above best_ask (or ask
        below best_bid), accidentally turning a maker order into a taker.
        """
        if not od.buy_orders or not od.sell_orders:
            return

        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())

        # Skew: negative when long, positive when short
        skew = int(round(-ACO_SKEW_K * (position - ACO_TARGET)))

        # Step 1: base passive price (inside spread, clamped to mu±1)
        # Step 2: apply skew
        # Step 3: re-clamp to ensure we stay inside the live spread (passive)
        bid_price = min(best_bid + 1, int(ACO_MU) - 1) + skew
        bid_price = min(bid_price, best_ask - 1)   # never cross best_ask

        ask_price = max(best_ask - 1, int(ACO_MU) + 1) + skew
        ask_price = max(ask_price, best_bid + 1)   # never cross best_bid

        if bid_price >= ask_price:
            return

        buy_room  = POSITION_LIMIT - position
        sell_room = POSITION_LIMIT + position

        if buy_room > 0:
            orders.append(Order("ASH_COATED_OSMIUM", bid_price,
                                min(ACO_MAKE_VOL, buy_room)))
        if sell_room > 0:
            orders.append(Order("ASH_COATED_OSMIUM", ask_price,
                                -min(ACO_MAKE_VOL, sell_room)))

    # ── ACO Strategy 2: mean-reversion aware MM ───────────────────────────────

    def _aco_make_rev(self, od, fv_make, position, orders):
        # type: (OrderDepth, float, int, List[Order]) -> None
        """
        Quotes centered on fv_make instead of raw mu.

        fv_make is already pulled toward mu (via ALPHA blend), so:
          - when microprice is high → fv_make < mid → our ask is lower than
            the raw mid+1 would be → we sell more eagerly, fading the move.
          - when microprice is low  → fv_make > mid → our bid is higher →
            we buy more eagerly, fading the move.

        With ACO_ALPHA=0.40, fv_make is more anchored to mu than before,
        so this effect is gentler — less overfitting to transient pressure.
        Combined with inventory skew, this is the core mean-reversion MM.
        """
        if not od.buy_orders or not od.sell_orders:
            return

        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        fv_int   = int(round(fv_make))

        # Inventory skew: flatten position toward ACO_TARGET over time
        skew = int(round(-ACO_SKEW_K * (position - ACO_TARGET)))

        # Clamp order: base → skew → re-clamp to spread (same as _aco_make_pure).
        # Without the final clamp a large skew can push the bid above best_ask.
        bid_price = min(best_bid + 1, fv_int - 1) + skew
        bid_price = min(bid_price, best_ask - 1)   # never cross best_ask

        ask_price = max(best_ask - 1, fv_int + 1) + skew
        ask_price = max(ask_price, best_bid + 1)   # never cross best_bid

        if bid_price >= ask_price:
            return

        buy_room  = POSITION_LIMIT - position
        sell_room = POSITION_LIMIT + position

        if buy_room > 0:
            orders.append(Order("ASH_COATED_OSMIUM", bid_price,
                                min(ACO_MAKE_VOL, buy_room)))
        if sell_room > 0:
            orders.append(Order("ASH_COATED_OSMIUM", ask_price,
                                -min(ACO_MAKE_VOL, sell_room)))

    # ── ACO Strategy 3: pure taking ───────────────────────────────────────────

    def _aco_take(self, od, fv_take, position, orders):
        # type: (OrderDepth, float, int, List[Order]) -> int
        """
        Hit asks below fv_take (cheap) and bids above fv_take (expensive).

        fv_take = mu + RHO*(fv_make - mu). With ACO_RHO=0.30, fv_take is only
        30% of the deviation from mu — much more conservative than before.
        Example: if microprice is 10004 → fv_make ≈ 10001.6 → fv_take ≈ 10000.48.
        We'd only buy asks at 10000 or sell bids at 10001+.  Very selective.
        """
        # Buy asks that look cheap vs fv_take, requiring 1-tick explicit edge buffer.
        # Condition: ask <= fv_take - 1, i.e., we need at least 1 full tick below
        # fv_take before crossing the spread. Prevents noisy fills on borderline ticks.
        for ask in sorted(od.sell_orders.keys()):
            if ask > fv_take - 1:
                break
            can_buy = POSITION_LIMIT - position
            if can_buy <= 0:
                break
            qty = min(-od.sell_orders[ask], can_buy)
            orders.append(Order("ASH_COATED_OSMIUM", ask, qty))
            position += qty

        # Sell bids that look expensive vs fv_take, same 1-tick buffer on the sell side.
        # Condition: bid >= fv_take + 1.
        for bid in sorted(od.buy_orders.keys(), reverse=True):
            if bid < fv_take + 1:
                break
            can_sell = POSITION_LIMIT + position
            if can_sell <= 0:
                break
            qty = min(od.buy_orders[bid], can_sell)
            orders.append(Order("ASH_COATED_OSMIUM", bid, -qty))
            position -= qty

        return position

    # ── ACO Strategy 4: naive mid-based MM ───────────────────────────────────

    def _aco_naive(self, od, position, orders):
        # type: (OrderDepth, int, List[Order]) -> None
        """
        Baseline strategy — mirrors the EMERALDS approach from the tutorial.

        FV = (best_bid + best_ask) / 2  (live mid each tick).

        Take: buy any ask strictly below FV; sell any bid strictly above FV.
          In practice, best_ask >= mid and best_bid <= mid always, so the taker
          leg only fires on crossed books or deep-level mispricing — rare but
          free edge when it occurs.

        Make: post at best_bid+1 (capped at FV-1) and best_ask-1 (floored at
          FV+1) with inventory skew. Earns spread income every fill.
        """
        if not od.buy_orders or not od.sell_orders:
            return

        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        mid      = (best_bid + best_ask) / 2.0
        fv_int   = int(round(mid))

        # --- Take leg ---
        for ask in sorted(od.sell_orders.keys()):
            if ask >= mid:
                break
            can_buy = POSITION_LIMIT - position
            if can_buy <= 0:
                break
            qty = min(-od.sell_orders[ask], can_buy)
            orders.append(Order("ASH_COATED_OSMIUM", ask, qty))
            position += qty

        for bid in sorted(od.buy_orders.keys(), reverse=True):
            if bid <= mid:
                break
            can_sell = POSITION_LIMIT + position
            if can_sell <= 0:
                break
            qty = min(od.buy_orders[bid], can_sell)
            orders.append(Order("ASH_COATED_OSMIUM", bid, -qty))
            position -= qty

        # --- Make leg ---
        skew = int(round(-ACO_SKEW_K * (position - ACO_TARGET)))

        bid_price = min(best_bid + 1, fv_int - 1) + skew
        bid_price = min(bid_price, best_ask - 1)   # never cross best_ask

        ask_price = max(best_ask - 1, fv_int + 1) + skew
        ask_price = max(ask_price, best_bid + 1)   # never cross best_bid

        if bid_price >= ask_price:
            return

        buy_room  = POSITION_LIMIT - position
        sell_room = POSITION_LIMIT + position

        if buy_room > 0:
            orders.append(Order("ASH_COATED_OSMIUM", bid_price,
                                min(ACO_MAKE_VOL, buy_room)))
        if sell_room > 0:
            orders.append(Order("ASH_COATED_OSMIUM", ask_price,
                                -min(ACO_MAKE_VOL, sell_room)))


# ════════════════════════════════════════════════════════════════════════════
# STRATEGY SUMMARY
# ════════════════════════════════════════════════════════════════════════════
#
# INTARIAN_PEPPER_ROOT (IPR)
# ──────────────────────────
# FV = IPR_FV_START + timestamp * 0.001
#   IPR_FV_START is estimated on tick 1: observe mid, subtract ts*slope,
#   snap to nearest 1000. Historical R²≈1 confirms the start is always a
#   multiple of 1000. Each 100-unit step → FV +0.1. Full day → FV +1000.
#
# No inventory management: holding IPR long is the optimal long-run strategy.
# Adding skew toward a target would reduce our long position and give up drift.
#
# "bh" — Buy-and-Hold (recommended):
#   Accumulate long at any ask (no FV gate — dynamic FV ≈ market, so gate
#   would block all buying). Never sell. Earns ~1000 ticks/unit/day.
#   Daily drift >> any MM spread income by ~500x.
#
# "take" — Two-sided taking (position-aware):
#   Not at limit: buy ALL asks first (no FV gate, drift makes any buy profitable),
#   then sell bids > FV (free edge, small position cost).
#   At limit: sell mispriced bids > FV first (frees room), then rebuy all asks.
#
# "make_sym" — Take + symmetric MM (gated by spread condition):
#   Profitable condition: live spread > 1 tick so room to quote inside.
#   Quotes at best_bid+1 / best_ask-1 clamped to FV±1.
#   Each fill earns ≥1 tick edge vs FV, exceeding drift_per_step (0.1).
#
# "make_asym" — Take + drift-biased asymmetric MM:
#   Same bid side as make_sym. Ask floor raised to FV + IPR_ASK_DRIFT_PREMIUM.
#   We only sell if someone bids ≥FV+2 above fair value, partially compensating
#   for the drift (0.1/step) we give up by parting with the unit.
#   No inventory skew — being long is always desirable.
#
# ASH_COATED_OSMIUM (ACO)
# ────────────────────────
# mu = 10000 (fixed), sigma ≈ 2.55, returns AR(1) with phi ≈ -0.50.
# Hurst on returns H=0.20 confirms mean-reversion. Spread ≈ 16 ticks.
#
# FV estimates (tuned to be less reactive):
#   microprice = (ask*bid_vol + bid*ask_vol) / (bid_vol + ask_vol)
#   fv_make    = 0.40*microprice + 0.60*mu   [ALPHA=0.40, down from 0.70]
#   fv_take    = mu + 0.30*(fv_make - mu)    [RHO=0.30, down from 0.50]
#   → fv_make stays very close to mu; fv_take is even more conservative.
#
# "make" — Pure passive MM:
#   Quotes at best_bid+1 / best_ask-1 clamped to mu±1 with inventory skew.
#
# "make_rev" — Mean-reversion aware MM:
#   Centers quotes on fv_make. With ALPHA=0.40 this effect is gentle —
#   fv_make moves ≤ 40% of any microprice deviation from mu.
#   Inventory skew flattens position toward ACO_TARGET=0.
#
# "take" — Pure taking:
#   Only hits orders mispriced vs fv_take. With RHO=0.50, moderate threshold.
#
# "hybrid" — Take then make (recommended):
#   First takes on fv_take (RHO=0.50, moderate conservatism).
#   Then posts passive quotes around fv_make (gentle mean-reversion, ALPHA=0.40).
#
# "naive" — Baseline mid-based MM (similar to tutorial EMERALDS strategy):
#   FV = live mid each tick. Take vs mid (rarely fires in normal market).
#   Make at best_bid+1 / best_ask-1 clamped to FV±1 with inventory skew.
#   Simplest possible MM; good benchmark to compare other strategies against.
# ════════════════════════════════════════════════════════════════════════════