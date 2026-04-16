# IMC Prosperity 4 — Preparation Notebook

A comprehensive self-study course for the [IMC Prosperity](https://prosperity.imc.com/) algorithmic trading competition, rebuilt from scratch after studying 10 top-team repositories from Prosperity 1–3.

---

## What This Is

IMC Prosperity is a 15-day online algorithmic trading competition where you submit a Python bot that runs on IMC's servers. Your bot receives a `TradingState` every ~100ms and must return buy/sell orders. Only the Python standard library is allowed in submissions — no NumPy, no Pandas, no SciPy.

This repo contains:

| File | Purpose |
|------|---------|
| `imc_prosperity_4_prep.ipynb` | Main self-study notebook (207 cells, 5 parts) |
| `datamodel.py` | Official IMC data model — required for local testing |
| `requirements.txt` | Local analysis dependencies (numpy, pandas, etc.) |
| `references/STUDY_NOTES.md` | Analysis of 10 winner repos from P1–P3 |

---

## Quick Start

```bash
# 1. Clone this repo
git clone https://github.com/VincentTLe/imc-prosperity-4-prep
cd imc-prosperity-4-prep

# 2. Install dependencies (for local analysis only — NOT for submission)
pip install -r requirements.txt
# or with uv:
uv pip install -r requirements.txt

# 3. Open the notebook
jupyter lab imc_prosperity_4_prep.ipynb
# or:
jupyter notebook imc_prosperity_4_prep.ipynb
```

> **Note:** When you submit to IMC, you only upload `trader.py`. The `datamodel.py` is pre-loaded on their servers — you do not submit it. But you **do** need it locally so your IDE and backtester work.

---

## Notebook Structure

The notebook follows an **Explain → Show → Do** pattern throughout. Every concept gets:
1. Plain-English explanation with analogy
2. A worked example in markdown (before any code)
3. A code demonstration
4. An exercise with solution

### Part 1 — Python Engineering
Everything you need to write a competition-quality bot:
- Python core syntax with order-book examples
- Data structures and performance (O(1) dict lookups vs O(n) list scans)
- Object-oriented programming and the real `datamodel.py` interface
- `traderData` serialization (your bot's only memory between ticks)
- Minimal Trader skeleton → full feature-rich version, built incrementally
- The `Logger` class (AWS Lambda truncates output at ~3,750 chars)

### Part 2 — Math & Statistics
All math done twice: pure Python (submission-safe) + NumPy (for analysis):
- Z-scores, rolling statistics, Bollinger Bands
- Simple Moving Average vs Exponential Moving Average
- Linear regression — pure Python least-squares
- Correlation vs cointegration (the "two drunk friends" analogy)
- Expected value, Kelly Criterion, and auction theory

### Part 3 — Trading Strategies
Seven complete strategies, each with backtest + visualization:
1. **Stable Market Making** — Wall Mid pricing, inventory skew, spread management
2. **Volatile Market Making** — VWAP, EMA, and popular-price fair value estimators
3. **Pairs / Statistical Arbitrage** — spread z-score, cointegrated products
4. **Basket Arbitrage** — PICNIC_BASKET1/2 vs their components
5. **Cross-Exchange Arbitrage** — import/export with conversion fees
6. **Options (Black-Scholes)** — `norm_cdf` (Abramowitz-Stegun), Greeks, IV bisection, vol smile
7. **Counterparty Identification** — detecting "Olivia" (informed trader who buys lows/sells highs)

### Part 4 — Manual Rounds
Prosperity has 5 manual trading rounds alongside the algorithmic ones:
- FX arbitrage (multi-currency chain optimization)
- Sealed-bid auctions (calculus derivation + grid search)
- Game theory (Nash equilibrium, crowd behavior)
- News sentiment (qualitative reasoning + Kelly sizing)

### Part 5 — Integration
- Multi-product Trader combining all strategies with a product router
- Monte Carlo augmentation to prevent backtest overfitting
- Cross-year data correlation analysis (Linear Utility discovered R²=0.99 between P2 and P3 data, worth ~2.1M SeaShells in one round)
- Competition day checklist and time management guide

---

## Key Files Explained

### `datamodel.py`

The official IMC data model. Your `Trader.run()` method receives a `TradingState` every tick:

```python
from datamodel import TradingState, Order, OrderDepth

class Trader:
    def run(self, state: TradingState):
        # state.order_depths  → {symbol: OrderDepth}
        # state.position      → {symbol: int}  (your current holdings)
        # state.own_trades    → fills from last tick
        # state.market_trades → all trades from last tick
        # state.traderData    → JSON string you returned last tick (your memory)
        # state.observations  → external market data

        orders = {}

        depth = state.order_depths.get("RAINFOREST_RESIN")
        if depth:
            best_bid = depth.best_bid()   # highest buy order in book
            best_ask = depth.best_ask()   # lowest sell order in book
            mid      = depth.mid_price()  # (best_bid + best_ask) / 2

            # Buy below fair value, sell above
            if best_ask < 10000:
                orders["RAINFOREST_RESIN"] = [Order("RAINFOREST_RESIN", best_ask, 10)]
            if best_bid > 10000:
                orders["RAINFOREST_RESIN"] = [Order("RAINFOREST_RESIN", best_bid, -10)]

        conversions = 0
        trader_data = ""
        return orders, conversions, trader_data
```

**Position limits** (your bot is rejected if you exceed these):

| Product | Limit |
|---------|-------|
| RAINFOREST_RESIN | ±50 |
| KELP | ±50 |
| SQUID_INK | ±50 |
| CROISSANTS | ±250 |
| JAMS | ±350 |
| DJEMBES | ±60 |
| PICNIC_BASKET1 | ±60 |
| PICNIC_BASKET2 | ±100 |
| MAGNIFICENT_MACARONS | ±75 |
| VOLCANIC_ROCK | ±400 |
| VOLCANIC_ROCK_VOUCHER_* | ±200 |

**Basket compositions:**
- `PICNIC_BASKET1` = 6 × CROISSANTS + 3 × JAMS + 1 × DJEMBES
- `PICNIC_BASKET2` = 4 × CROISSANTS + 2 × JAMS

### `requirements.txt`

For **local analysis only**. Never import these in your submission:

```
numpy, pandas, matplotlib, scipy    ← data analysis
jupyter, notebook, jupyterlab       ← notebook environment
nbconvert, ipywidgets               ← notebook tooling
```

---

## Key Patterns from Winner Teams

These patterns appear across nearly every top-3 finisher:

### 1. The Three-Phase Execution Loop

```python
def run(self, state):
    orders = []

    # Phase 1: TAKE — aggressively fill mispriced orders in the book
    for price, volume in state.order_depths["PRODUCT"].sell_orders.items():
        if price < fair_value:
            orders.append(Order("PRODUCT", price, -volume))  # buy their ask

    # Phase 2: CLEAR — reduce risky position with zero-EV trades
    position = state.position.get("PRODUCT", 0)
    if position > 10:
        orders.append(Order("PRODUCT", fair_value, -position))  # sell to clear

    # Phase 3: MAKE — post passive quotes to collect the spread
    orders.append(Order("PRODUCT", fair_value - 2, buy_qty))   # bid
    orders.append(Order("PRODUCT", fair_value + 2, -sell_qty)) # ask

    return {"PRODUCT": orders}, 0, ""
```

### 2. Wall Mid (more stable than simple midpoint)

```python
# Simple midpoint is vulnerable to pennying attacks
# Wall Mid uses the price where the most volume sits
best_bid_price = max(depth.buy_orders, key=depth.buy_orders.get)
best_ask_price = min(depth.sell_orders, key=depth.sell_orders.get)  # by |volume|
wall_mid = (best_bid_price + best_ask_price) / 2
```
*Source: Frankfurt Hedgehogs, 2nd place Prosperity 3*

### 3. Submission-Safe `norm_cdf` (Abramowitz-Stegun)

```python
import math

def norm_cdf(x: float) -> float:
    """Normal CDF using Abramowitz-Stegun approximation (max error 1.5e-7).
    No scipy needed — works inside the competition environment."""
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2.0)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)
```
*Used by all top-3 teams across P2 and P3 for Black-Scholes options pricing.*

### 4. Logger (AWS Lambda output limit)

```python
class Logger:
    """IMC truncates your bot's stdout at ~3,750 characters per tick."""
    def __init__(self):
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects, sep=" ", end="\n"):
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state, orders, conversions, trader_data):
        output = json.dumps([state.toJSON(), orders, conversions, trader_data, self.logs],
                            cls=ProsperityEncoder, separators=(',', ':'))
        print(output[:self.max_log_length])
        self.logs = ""

logger = Logger()
```

---

## Common Mistakes (from winner post-mortems)

1. **Strategy leakage on Discord** — Linear Utility dropped from 3rd to 17th after sharing details mid-competition.
2. **`list.pop(0)` for rolling windows** — O(n) each call; use `collections.deque(maxlen=N)` instead.
3. **Linear regression in price space** — Prices are near-collinear and unstable. Regress on spreads or returns instead.
4. **Trusting sunlight/humidity as signals** — These were spurious features in P3 (MAGNIFICENT_MACARONS).
5. **Incomplete delta hedging** — Hedging options positions naively can cost more than the premium earned.
6. **Exceeding position limits** — Orders beyond your limit are silently rejected by the exchange.
7. **`traderData` exceeding ~100KB** — Causes your bot to crash and return no orders for that tick.
8. **`print()` output exceeding ~3,750 chars** — Silently truncated; use the Logger class instead.
9. **No position clearing phase** — Without a clearing phase, you get stuck at position limits and can't trade.

---

## References Studied

The notebook and study notes are informed by code from these repositories:

| Repo | Team / Finisher | Competition |
|------|-----------------|-------------|
| [ericcccsliu/imc-prosperity-2](https://github.com/ericcccsliu/imc-prosperity-2) | Linear Utility — 2nd place | Prosperity 2 |
| [jmerle/imc-prosperity-2](https://github.com/jmerle/imc-prosperity-2) | jmerle — 9th place | Prosperity 2 |
| [pe049395/IMC-Prosperity-2024](https://github.com/pe049395/IMC-Prosperity-2024) | pe049395 — 13th place | Prosperity 2 |
| [gabsens/IMC-Prosperity-2-Manual](https://github.com/gabsens/IMC-Prosperity-2-Manual) | Manual round solutions | Prosperity 2 |
| [TimoDiehm/imc-prosperity-3](https://github.com/TimoDiehm/imc-prosperity-3) | Frankfurt Hedgehogs — 2nd place | Prosperity 3 |
| [chrispyroberts/imc-prosperity-3](https://github.com/chrispyroberts/imc-prosperity-3) | chrispyroberts — 7th place | Prosperity 3 |
| [CarterT27/imc-prosperity-3](https://github.com/CarterT27/imc-prosperity-3) | Alpha Animals — 9th place | Prosperity 3 |
| [jmerle/imc-prosperity-3-backtester](https://github.com/jmerle/imc-prosperity-3-backtester) | jmerle's backtester | Prosperity 3 |
| [jmerle/imc-prosperity-3-visualizer](https://github.com/jmerle/imc-prosperity-3-visualizer) | jmerle's visualizer | Prosperity 3 |
| [amogh18t/IMC-Prosperity](https://github.com/amogh18t/IMC-Prosperity) | amogh18t | Prosperity 1 |

Full analysis with code snippets and attributed strategies: [`references/STUDY_NOTES.md`](references/STUDY_NOTES.md)

---

## License

Educational use. Winner code snippets are attributed to their original authors above.
