# Study Notes: IMC Prosperity 1-3 Winner/Reference Repos

> Compiled from analysis of 10 repos across Prosperity 1, 2, and 3.
> Purpose: Extract reusable patterns, code snippets, and strategic insights for Prosperity 4.

---

## Table of Contents

1. [Repos Studied](#repos-studied)
2. [The Real datamodel.py](#the-real-datamodelpy)
3. [norm_cdf (Abramowitz-Stegun)](#norm_cdf-abramowitz-stegun)
4. [Logger Class (2000 Char Budget)](#logger-class-2000-char-budget)
5. [Three-Phase Execution (TAKE-CLEAR-MAKE)](#three-phase-execution-take-clear-make)
6. [Wall Mid Pricing](#wall-mid-pricing)
7. [Olivia / Counterparty Detection](#olivia--counterparty-detection)
8. [Implied Volatility Solvers](#implied-volatility-solvers)
9. [Product Parameters (Prosperity 3)](#product-parameters-prosperity-3)
10. [Key Strategic Insights](#key-strategic-insights)
11. [Tools](#tools)

---

## Repos Studied

### Prosperity 1

| Repo | Placement | Notes |
|------|-----------|-------|
| **amogh18t** | -- | Basic bot. Provides `datamodel.py` for P1 reference. |

### Prosperity 2

| Repo | Placement | Notes |
|------|-----------|-------|
| **Linear Utility** | 2nd | Cross-year data correlation (R^2=0.99), three-phase execution (TAKE/CLEAR/MAKE), mean-reversion beta=-0.229, strategy leakage warning. |
| **jmerle** | 9th | Community tools author (backtester, visualizer), counterparty pattern recognition, famously competed from his phone. |
| **pe049395** | 13th | Expected utility framework, 8 strategy modules, `Status` class pattern, Monte Carlo validation. |
| **gabsens** | 30th (Manual) | Mathematical Jupyter notebooks for manual round optimization. |

### Prosperity 3

| Repo | Placement | Notes |
|------|-----------|-------|
| **Frankfurt Hedgehogs** | 2nd | Wall Mid pricing, IV scalping (100-150k/round), taker bot exploit, three-phase execution, Olivia detection persisted in traderData, `statistics.NormalDist` for Black-Scholes. |
| **Alpha Animals** | 9th | Abramowitz-Stegun `norm_cdf`, Newton-Raphson IV solver with caching, full Olivia copy-trading system, Logger class with binary-search truncation. |
| **chrispyroberts** | 7th | Rolling window IV outperformed quadratic fitting by 170k/day; market-maker mid > model-based fair value. |

### Tools

| Repo | Purpose |
|------|---------|
| **jmerle/imc-prosperity-3-backtester** | Python backtester for local testing. |
| **jmerle/imc-prosperity-3-visualizer** | Web visualizer for trade analysis. |

---

## The Real datamodel.py

The `datamodel.py` file defines every class the platform passes into `Trader.run()`. Understanding it is non-negotiable. Below is the Prosperity 3 version with annotations.

**Key changes between years:**
- P2 had `sunlight` and `humidity` fields on `ConversionObservation`.
- P3 replaced those with `sugarPrice` and `sunlightIndex`.
- The core classes (`TradingState`, `Order`, `OrderDepth`, `Trade`) have been stable across all years.

```python
import json
from dataclasses import dataclass, field
from typing import Dict, List

Time = int
Symbol = str
Product = str
Position = int
UserId = str
ObservationValue = int

# --- Listing ---
@dataclass
class Listing:
    symbol: Symbol
    product: Product
    denomination: Symbol

# --- ConversionObservation ---
@dataclass
class ConversionObservation:
    bidPrice: float
    askPrice: float
    transportFees: float
    exportTariff: float
    importTariff: float
    sugarPrice: float       # P3-specific (was sunlight in P2)
    sunlightIndex: float    # P3-specific (was humidity in P2)

# --- Observation ---
@dataclass
class Observation:
    plainValueObservations: Dict[Product, ObservationValue]
    conversionObservations: Dict[Product, ConversionObservation]

# --- Order ---
@dataclass
class Order:
    symbol: Symbol
    price: int
    quantity: int  # positive = BUY, negative = SELL

    def __repr__(self):
        side = "BUY" if self.quantity > 0 else "SELL"
        return f"({side} {abs(self.quantity)}x {self.price})"

# --- OrderDepth ---
@dataclass
class OrderDepth:
    buy_orders: Dict[int, int] = field(default_factory=dict)   # price -> qty (positive)
    sell_orders: Dict[int, int] = field(default_factory=dict)  # price -> qty (negative!)

# --- Trade ---
@dataclass
class Trade:
    symbol: Symbol
    price: int
    quantity: int
    buyer: UserId = ""
    seller: UserId = ""
    timestamp: int = 0

# --- TradingState ---
@dataclass
class TradingState:
    traderData: str                                 # your persisted state (JSON string)
    timestamp: Time
    listings: Dict[Symbol, Listing]
    order_depths: Dict[Symbol, OrderDepth]
    own_trades: Dict[Symbol, List[Trade]]
    market_trades: Dict[Symbol, List[Trade]]
    position: Dict[Product, Position]
    observations: Observation

# --- JSON Encoder ---
class ProsperityEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (Listing, Observation, ConversionObservation,
                          Order, OrderDepth, Trade, TradingState)):
            return o.__dict__
        return super().default(o)
```

**Critical details:**
- `sell_orders` quantities are **negative**. Always use `abs()` when computing fill sizes.
- `traderData` is a string. You must serialize/deserialize (JSON) yourself. It persists across ticks.
- `position` may not contain a key for products you have never traded. Always use `.get(product, 0)`.

---

## norm_cdf (Abramowitz-Stegun)

Used by **ALL** top teams for Black-Scholes option pricing (vouchers). Two approaches observed:

### Approach A: Abramowitz-Stegun Approximation (Alpha Animals, chrispyroberts)

This is a direct polynomial approximation. No imports needed. Fast and deterministic.

```python
def norm_cdf(x: float) -> float:
    """Abramowitz-Stegun approximation to the cumulative normal distribution."""
    a1 =  0.254829592
    a2 = -0.284496736
    a3 =  1.421413741
    a4 = -1.453152027
    a5 =  1.061405429
    p  =  0.3275911

    sign = 1.0
    if x < 0:
        sign = -1.0
    x = abs(x) / (2.0 ** 0.5)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * (
        2.718281828459045 ** (-x * x)
    )

    return 0.5 * (1.0 + sign * y)
```

### Approach B: statistics.NormalDist (Frankfurt Hedgehogs)

Simpler, uses the standard library. Slightly slower but negligible at competition scale.

```python
from statistics import NormalDist

NORM = NormalDist()

def norm_cdf(x: float) -> float:
    return NORM.cdf(x)

def norm_pdf(x: float) -> float:
    return NORM.pdf(x)
```

**Recommendation:** Use Abramowitz-Stegun. It avoids import overhead and is battle-tested by the majority of top finishers.

---

## Logger Class (2000 Char Budget)

The platform enforces a **2000 character limit** on the string returned by `Trader.run()` for logging. Alpha Animals solved this with a Logger class that uses binary-search truncation to fit within the budget.

```python
import json

class Logger:
    CHAR_LIMIT = 2000

    def __init__(self):
        self.logs = ""
        self.max_log_length = self.CHAR_LIMIT

    def print(self, *objects, sep=" ", end="\n"):
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state, orders, conversions, trader_data):
        """Called at the end of Trader.run(). Returns the log string."""
        base_length = len(self._prefix(state, orders, conversions, trader_data))

        # Binary search for max log length that fits
        lo, hi = 0, len(self.logs)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if base_length + mid <= self.CHAR_LIMIT:
                lo = mid
            else:
                hi = mid - 1

        # Build the final output
        output = self._prefix(state, orders, conversions, trader_data)
        output = output.replace("__LOGS__", self.logs[:lo])

        self.logs = ""
        return output

    def _prefix(self, state, orders, conversions, trader_data):
        return (
            json.dumps([
                self._compress_state(state, trader_data),
                self._compress_orders(orders),
                conversions,
                "__LOGS__",
            ], cls=ProsperityEncoder, separators=(",", ":"))
        )

    def _compress_state(self, state, trader_data):
        """Omits own_trades and market_trades to save space."""
        return [
            state.timestamp,
            trader_data,
            {s: [d.buy_orders, d.sell_orders] for s, d in state.order_depths.items()},
            # own_trades and market_trades intentionally omitted
        ]

    def _compress_orders(self, orders):
        return {s: [[o.price, o.quantity] for o in ol] for s, ol in orders.items()}
```

**Key design decisions:**
- `_compress_state` omits `own_trades` and `market_trades` to save characters.
- Binary search finds the exact maximum log length that fits within the 2000-char budget.
- The visualizer (jmerle) expects a specific JSON format; this Logger is compatible with it.

---

## Three-Phase Execution (TAKE-CLEAR-MAKE)

This is the dominant order-generation pattern among top teams. Originated (or at least popularized) by **Linear Utility (P2, 2nd place)** and also used by **Frankfurt Hedgehogs (P3, 2nd place)**.

### Phase 1: TAKE (Aggress on Mispriced Orders)

Walk the book and lift/hit any orders that are better than your fair value.

```python
def take_best_orders(product, fair_value, order_depth, position, limit):
    """Aggress on mispriced orders in the book."""
    orders = []
    pos = position

    # Take sells (buy from sellers offering below fair value)
    for price in sorted(order_depth.sell_orders.keys()):
        if price >= fair_value:
            break
        available = abs(order_depth.sell_orders[price])
        can_buy = limit - pos
        qty = min(available, can_buy)
        if qty > 0:
            orders.append(Order(product, price, qty))
            pos += qty

    # Take buys (sell to buyers bidding above fair value)
    for price in sorted(order_depth.buy_orders.keys(), reverse=True):
        if price <= fair_value:
            break
        available = order_depth.buy_orders[price]
        can_sell = limit + pos  # pos is negative when short
        qty = min(available, can_sell)
        if qty > 0:
            orders.append(Order(product, price, -qty))
            pos -= qty

    return orders, pos
```

### Phase 2: CLEAR (Flatten Inventory at Fair Value)

Place orders at fair value to reduce position toward zero. These are zero-EV trades that free up capacity for the next tick.

```python
def clear_position(product, fair_value, position):
    """Place orders at fair value to reduce inventory."""
    orders = []
    if position > 0:
        orders.append(Order(product, int(fair_value), -position))
    elif position < 0:
        orders.append(Order(product, int(fair_value) + 1, -position))
    return orders
```

### Phase 3: MAKE (Post Passive Quotes)

Place resting limit orders around fair value to earn the spread.

```python
def market_make(product, fair_value, position, limit, spread=2):
    """Post passive quotes around fair value."""
    orders = []
    half = spread // 2

    bid_price = int(fair_value) - half
    ask_price = int(fair_value) + half

    bid_qty = limit - position
    ask_qty = limit + position

    if bid_qty > 0:
        orders.append(Order(product, bid_price, bid_qty))
    if ask_qty > 0:
        orders.append(Order(product, ask_price, -ask_qty))

    return orders
```

### Why This Pattern Works

1. **TAKE** captures immediate edge (arbitrage / mispricing).
2. **CLEAR** prevents position limits from blocking future trades.
3. **MAKE** passively earns spread when no mispricing exists.

The position is tracked through all three phases so that limit constraints are respected across the combined order set.

---

## Wall Mid Pricing

**Frankfurt Hedgehogs (P3, 2nd place)** introduced "Wall Mid" as a superior fair-value estimate for market-making. Instead of using the simple mid (best bid + best ask) / 2, they use the walls -- the extreme resting orders that define the book's boundaries.

### Concept

```
bid_wall = min(buy_orders.keys())    # lowest bid (the "wall")
ask_wall = max(sell_orders.keys())   # highest ask (the "wall")
wall_mid = (bid_wall + ask_wall) / 2
```

The intuition: the outermost orders represent the true support/resistance levels. The best bid/ask can be noisy or manipulated, but the walls are more stable anchors.

### Execution: Penny Inside the Walls

Once you have `wall_mid`, you place orders just inside the walls:

```python
our_bid = bid_wall + 1    # penny inside the bid wall
our_ask = ask_wall - 1    # penny inside the ask wall
```

### Volume-Weighted Adjustment

Frankfurt Hedgehogs also adjusted based on volume imbalance:

- If heavy volume on the bid side, shade `wall_mid` upward (overbid).
- If heavy volume on the ask side, shade `wall_mid` downward (underbid).

This captures the informational content of where liquidity is concentrated.

---

## Olivia / Counterparty Detection

Several teams discovered that specific counterparty names (notably "Olivia") are reliable directional signals. The game engine includes bot traders with consistent behavioral patterns that can be exploited.

### Frankfurt Hedgehogs: Timestamp-Based Olivia Detection

Persist buy/sell timestamps in `traderData` and derive Olivia's directional stance.

```python
# In traderData (persisted as JSON):
# { "olivia_buys": [100, 300, 500], "olivia_sells": [200] }

def detect_olivia_direction(state):
    """Derive Olivia's direction from recent trade timestamps."""
    data = json.loads(state.traderData) if state.traderData else {}
    olivia_buys = data.get("olivia_buys", [])
    olivia_sells = data.get("olivia_sells", [])

    # Scan market_trades for Olivia activity
    for product in state.market_trades:
        for trade in state.market_trades[product]:
            if trade.buyer == "Olivia":
                olivia_buys.append(trade.timestamp)
            if trade.seller == "Olivia":
                olivia_sells.append(trade.timestamp)

    # Determine direction from recent activity
    recent_buys = [t for t in olivia_buys if t > state.timestamp - 3000]
    recent_sells = [t for t in olivia_sells if t > state.timestamp - 3000]

    if len(recent_buys) > len(recent_sells):
        direction = "LONG"
    elif len(recent_sells) > len(recent_buys):
        direction = "SHORT"
    else:
        direction = "NEUTRAL"

    return direction, olivia_buys, olivia_sells
```

### Alpha Animals: Full Copy-Trading System

Alpha Animals went further, building a regime-tracking system per product:

```python
# Tracked per product in traderData:
# insider_regimes = { "SQUID_INK": "LONG", "KELP": "NEUTRAL", ... }

# When Olivia is LONG -> bias our position long
# When Olivia is SHORT -> bias our position short
# When NEUTRAL -> revert to default market-making
```

**Key insight:** Olivia is a consistently profitable signal. Ignoring counterparty information leaves significant edge on the table.

---

## Implied Volatility Solvers

Options pricing (vouchers on VOLCANIC_ROCK in P3) requires computing implied volatility. Three approaches were observed:

### Approach A: Newton-Raphson (Alpha Animals)

Iterative solver. Robust with clamping and caching.

```python
def implied_volatility(call_price, S, K, T, r=0.0):
    """Newton-Raphson IV solver with clamping and caching."""
    sigma = 0.3  # initial guess

    for _ in range(50):
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        bs_price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        vega = S * norm_pdf(d1) * math.sqrt(T)

        if vega < 1e-10:
            break

        sigma -= (bs_price - call_price) / vega
        sigma = max(0.01, min(sigma, 2.0))  # clamp to [0.01, 2.0]

    return sigma
```

**Notes:**
- Alpha Animals cached IV results to avoid recomputing every tick.
- 50 iterations is generous; most converge in fewer than 10.
- Clamping to `[0.01, 2.0]` prevents numerical instability.

### Approach B: Pre-Fitted Quadratic (Frankfurt Hedgehogs)

Skip Newton-Raphson entirely. Fit a quadratic polynomial on `log(K/S)` (log-moneyness) using historical data, then evaluate the polynomial at runtime.

```python
# Pre-fitted coefficients (example):
# IV(m) = a * m^2 + b * m + c
# where m = log(K / S)

def iv_from_quadratic(S, K, a, b, c):
    m = math.log(K / S)
    return a * m**2 + b * m + c
```

**Trade-off:** Faster at runtime, but the fit must be updated if the volatility surface shifts.

### Approach C: Rolling Window IV (chrispyroberts)

chrispyroberts found that computing IV from a rolling window of recent option trades **outperformed** the quadratic curve fitting approach by **170,000 PnL per day**.

Additionally, chrispyroberts found that using the raw **market-maker mid** as fair value beat model-derived fair values in practice.

**Takeaway:** Simpler, more adaptive methods can outperform theoretically elegant ones. Test empirically.

---

## Product Parameters (Prosperity 3)

### Round-by-Round Product Introduction

| Round | Products Added |
|-------|---------------|
| 1 | RAINFOREST_RESIN, KELP, SQUID_INK |
| 2 | CROISSANTS, JAMS, DJEMBES, PICNIC_BASKET1, PICNIC_BASKET2 |
| 3 | MAGNIFICENT_MACARONS (cross-exchange) |
| 4 | VOLCANIC_ROCK, VOUCHERS (options) |

### Position Limits

| Product | Limit | Characteristics |
|---------|-------|-----------------|
| RAINFOREST_RESIN | 50 | Stable, fair value = 10,000 |
| KELP | 50 | Volatile |
| SQUID_INK | 50 | Mean-reverting |
| CROISSANTS | 250 | Basket component |
| JAMS | 350 | Basket component |
| DJEMBES | 60 | Basket component |
| PICNIC_BASKET1 | 60 | = 6 CROISSANTS + 3 JAMS + 1 DJEMBES |
| PICNIC_BASKET2 | 100 | = 4 CROISSANTS + 2 JAMS |
| MAGNIFICENT_MACARONS | 75 | Cross-exchange arbitrage via conversions |
| VOLCANIC_ROCK | 400 | Underlying for vouchers |
| VOUCHERS | 200 | European call options on VOLCANIC_ROCK |

### Basket Compositions

```
PICNIC_BASKET1 = 6 * CROISSANTS + 3 * JAMS + 1 * DJEMBES
PICNIC_BASKET2 = 4 * CROISSANTS + 2 * JAMS
```

Basket arbitrage: compute synthetic fair value from components, trade the basket when it deviates.

### RAINFOREST_RESIN

The simplest product. Fair value is fixed at **10,000**. Pure market-making:
- Bid at 9,998, ask at 10,002.
- Take any orders that cross fair value.
- This is the "warm-up" product every team should maximize first.

### MAGNIFICENT_MACARONS (Cross-Exchange)

Traded via `ConversionObservation`. The conversion mechanism allows buying on a foreign exchange and selling locally (or vice versa), subject to transport fees, tariffs, and position limits.

**Key finding (Frankfurt Hedgehogs):** The `sugarPrice` and `sunlightIndex` fields in `ConversionObservation` are **NOT** useful trading signals for MACARONS. Teams that tried to use them as predictors found no edge.

### Frankfurt Hedgehogs' Taker Bot Exploit

Frankfurt Hedgehogs identified a taker bot in the simulation that would buy at:

```python
taker_price = int(external_bid + 0.5)
```

By understanding this bot's pricing, they could position their asks to get filled reliably.

---

## Key Strategic Insights

### 1. Cross-Year Data Correlation (R^2 = 0.99)

**Source:** Linear Utility (P2, 2nd place)

Price series from one year's competition can predict the next year's prices with near-perfect correlation. Linear Utility discovered a **1.25x multiplier** between P1 and P2 data:

```
P2_price ~= 1.25 * P1_price
```

This single insight was worth **2.1 million PnL** in a single round. If Prosperity 4 follows the same pattern, analyzing P3 price data could provide a massive edge.

**Action item:** Obtain P3 price data and look for correlations with any early P4 data.

### 2. Strategy Leakage = Death

**Source:** Linear Utility (P2, 2nd place)

Linear Utility shared strategy details on Discord mid-competition and dropped from **3rd to 17th place** as competitors copied their approach. The edge evaporated within a single round.

**Lesson:** Never share specific strategy details (parameters, signals, thresholds) publicly during the competition. General concepts are fine; exact implementations are not.

### 3. Simple Beats Complex

**Source:** Stanford Cardinal (P3), chrispyroberts (P3, 7th place)

- Stanford Cardinal found that **simple linear regression on 4-5 recent timestamps** beat complex predictive models for price forecasting.
- chrispyroberts found that **rolling window IV** beat quadratic curve fitting by 170k/day, and that **raw market-maker mid** beat model-derived fair values.

**Lesson:** Start with the simplest possible approach. Only add complexity when you have empirical evidence it helps. Over-fitting to historical data is a persistent risk.

### 4. Position Clearing is Essential

Across all top teams, actively clearing positions (even at zero EV) is critical. If your position is at the limit, you cannot take new trades. A zero-EV clearing trade that frees capacity for a profitable trade next tick is net positive.

The CLEAR phase in the three-phase execution pattern exists specifically for this reason.

### 5. Mean Reversion (beta = -0.229)

**Source:** Linear Utility (P2, 2nd place)

For mean-reverting products (e.g., SQUID_INK in P3), a beta coefficient of approximately **-0.229** was effective. The signal:

```python
fair_value_adjustment = beta * (current_position / position_limit)
```

This biases your fair value to encourage trades that reduce your position.

### 6. IV Scalping Returns

**Source:** Frankfurt Hedgehogs (P3, 2nd place)

Options market-making on VOUCHERS produced **100,000-150,000 PnL per round** for Frankfurt Hedgehogs. This was one of the highest-returning strategies in P3.

### 7. Backtesting Infrastructure Matters

**Source:** jmerle (P2, 9th place)

Having a local backtester and visualizer dramatically accelerates iteration speed. jmerle's tools (backtester + visualizer) became community standards. Setting up local testing infrastructure should be a Day 1 priority.

---

## Tools

### jmerle/imc-prosperity-3-backtester

Python-based local backtester. Simulates the trading engine locally so you can test strategies without submitting to the platform.

**Location:** `references/p3-backtester/`

**Usage:**
```bash
pip install imc-prosperity3-backtester
prosperity3bt <algo_file.py>
```

### jmerle/imc-prosperity-3-visualizer

Web-based visualizer for analyzing trades, PnL, and order book state. Parses the JSON logs produced by the Logger class.

**Location:** `references/p3-visualizer/`

**Usage:** Open the hosted version or run locally. Upload your algorithm's log output to visualize trades against the order book.

---

## Quick Reference: Code Snippet Checklist

When building a new algorithm for Prosperity 4, ensure you have implementations of:

- [ ] `datamodel.py` classes (or import from platform)
- [ ] `norm_cdf` (Abramowitz-Stegun)
- [ ] `Logger` class (2000 char budget, binary-search truncation)
- [ ] Three-phase execution: `take_best_orders`, `clear_position`, `market_make`
- [ ] `traderData` serialization/deserialization (JSON)
- [ ] Counterparty detection (scan `market_trades` for known bot names)
- [ ] IV solver (Newton-Raphson with clamping)
- [ ] Black-Scholes pricer (using `norm_cdf`)
- [ ] Basket arbitrage calculator (synthetic vs. market price)
- [ ] Position tracking through all phases (respect limits)

---

## Source Attribution

| Pattern | Primary Source | Repo Path |
|---------|---------------|-----------|
| Three-Phase Execution | Linear Utility (P2, 2nd) | `references/p2-linear-utility-2nd/` |
| Wall Mid Pricing | Frankfurt Hedgehogs (P3, 2nd) | `references/p3-frankfurt-hedgehogs-2nd/` |
| Olivia Detection | Frankfurt Hedgehogs + Alpha Animals | `references/p3-frankfurt-hedgehogs-2nd/`, `references/p3-alpha-animals-9th/` |
| norm_cdf (A-S) | Alpha Animals (P3, 9th) | `references/p3-alpha-animals-9th/` |
| Logger Class | Alpha Animals (P3, 9th) | `references/p3-alpha-animals-9th/` |
| IV Solver (N-R) | Alpha Animals (P3, 9th) | `references/p3-alpha-animals-9th/` |
| IV Quadratic Fit | Frankfurt Hedgehogs (P3, 2nd) | `references/p3-frankfurt-hedgehogs-2nd/` |
| Rolling Window IV | chrispyroberts (P3, 7th) | `references/p3-chrispyroberts-7th/` |
| Cross-Year Correlation | Linear Utility (P2, 2nd) | `references/p2-linear-utility-2nd/` |
| Backtester | jmerle (P2, 9th) | `references/p3-backtester/` |
| Visualizer | jmerle (P2, 9th) | `references/p3-visualizer/` |
| Expected Utility Framework | pe049395 (P2, 13th) | `references/p2-pe049395-13th/` |
| Manual Round Math | gabsens (P2, Manual 30th) | `references/p2-manual-solutions/` |
| P1 datamodel.py | amogh18t (P1) | `references/p1-amogh18t/` |
