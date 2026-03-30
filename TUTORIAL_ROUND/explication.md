# IMC Prosperity 4 - Tutorial Round Strategy

**Round:** Tutorial (Round 0)  
**Products:** EMERALDS, TOMATOES

---

## 📊 Overview

This repository contains our algorithmic trading strategy for the **IMC Prosperity 4 Tutorial Round**. The strategy implements a robust market making approach with product-specific fair value estimation and risk management.

### Core Components

1. **Fair Price Estimation** — Product-specific valuation methods
2. **Market Making** — Spread capture via penny jumping
3. **Position Management** — Risk control with conditional trading
4. **Order Flow Analysis** — [Future enhancement]

**Objective:** Balance profitability and risk control while maintaining consistent execution in the order book.

---

## 🎯 Strategy Details

### 1. Fair Price Estimation

Fair value calculation is **product-specific** based on market characteristics:

#### EMERALDS (Stationary Product)

```python
fair_value = 10000  # Constant
```

- **Characteristics:** Stationary price that does not move
- **Market behavior:** Consistently trades around 10,000
- **Method:** Simple BBO mid-price for reference
- **Rationale:** No need for sophisticated estimation — price is stable

---

#### TOMATOES (Non-Stationary Product)

**Method:** Wall Mid + EMA

```python
# Step 1: Compute Wall Mid
wall_bid = price at bid level with maximum volume
wall_ask = price at ask level with maximum volume
wall_mid = (wall_bid + wall_ask) / 2

# Step 2: Apply EMA smoothing
alpha = 0.1
fair_value = alpha × wall_mid + (1 - alpha) × previous_ema
```

**Why Wall Mid?**
- BBO (best bid/offer) is noisy due to ephemeral small orders
- Deepest levels (highest volume) represent true liquidity
- Reduces noise by **~50%** (σ: 1.34 → 0.67)

**Why EMA?**
- Smooths out remaining volatility
- Filters false mean reversion signals
- Provides stable reference for trading decisions

**Validation:**
- Autocorrelation analysis confirms reduced noise
- CMU Physics team validation: wall mid eliminates artifacts from ephemeral orders

---

### 2. Market Making (Spread Capture)

We continuously place buy and sell orders around the fair price using **penny jumping** for queue priority.

#### Strategy

```python
bid_price = best_bid + 1   # Jump ahead in the queue
ask_price = best_ask - 1   # Jump ahead in the queue
```

**Constraint:** Only post orders that remain profitable relative to fair value.

#### Example: EMERALDS

```
Fair value: 10,000
Best bid: 9,996 → We post at 9,997
Best ask: 10,004 → We post at 10,003

Result: Queue priority + 3 tick edge on each side
```

#### Example: TOMATOES

```
Fair value (EMA): 5,006.5
Best bid: 5,005 (< fair_value) → We post at 5,006 (best_bid + 1)
Best ask: 5,008 (> fair_value) → We post at 5,007 (best_ask - 1)

Result: Queue priority + profitable spreads
```

---

### 3. Position Management (Inventory Control)

We use a **conditional approach** inspired by the CMU Physics team's winning strategy from Prosperity 3.

#### Position-Reducing at Fair Value

**Rule:** Only take fair-value trades that **shrink |position|**

```python
IF position > 0 (LONG):
    post_buy  = True  IF buy_price < fair_value   # Only if edge exists
    post_sell = True  ALWAYS                       # Reduces position OR has edge

IF position < 0 (SHORT):
    post_buy  = True  ALWAYS                       # Reduces position OR has edge
    post_sell = True  IF sell_price > fair_value  # Only if edge exists
```

#### Example Scenario

```
Situation:
  - Position: -20 (short)
  - Fair value: 10,000
  - Best ask: 10,000 (at fair value)

Decision: BUY 15 @ 10,000

Rationale:
  - No profit (price = fair value)
  - BUT reduces position: -20 → -5 (75% less risk)
  
Cost: 0 seashells
Benefit: Way less risk
```

#### Why This Approach?

✅ Always takes trades with an edge (price ≠ fair value)  
✅ Only takes fair-value trades that reduce exposure  
✅ Prevents accumulating dangerous positions  
✅ No complex skew calculations needed  
✅ Validated by CMU's winning team

---

### 4. Order Flow / Trader Following

**Status:** Not implemented in tutorial round

**Future Enhancement:** Monitor market trades to detect participant behavior patterns.

Potential signals:
- Consistent buying/selling by specific traders
- Volume-weighted order flow
- Momentum indicators

---

## 📈 Key Parameters

| Product | Fair Value Method | Position Limit | Alpha (EMA) | Penny Jump |
|---------|-------------------|----------------|-------------|------------|
| **EMERALDS** | Constant: 10,000 | 20 | N/A | ±1 tick |
| **TOMATOES** | Wall Mid + EMA | 15 | 0.1 | ±1 tick |

---

## 🏗️ Implementation

### File Structure

```
.
├── trader.py              # Main trading algorithm
├── datamodel.py           # IMC-provided data structures
├── prices_round_0_day_1.csv
├── prices_round_0_day_2.csv
├── visualize_simple.py    # Data visualization script
└── README.md
```

### Core Functions

```python
def compute_wall_mid(order_depth):
    """Calculate wall mid from deepest book levels"""
    # Find bid/ask with maximum volume
    # Return (wall_bid + wall_ask) / 2

def update_ema(wall_mid, previous_ema, alpha=0.1):
    """Update exponential moving average"""
    return alpha * wall_mid + (1 - alpha) * previous_ema

def should_post_order(position, order_type, order_price, fair_value):
    """Determine if order should be posted based on position"""
    # Implement conditional logic for position-reducing
```

---

## 🧪 Testing

### Local Backtesting

```bash
prosperity4btx trader.py 0 --vis
```

### Data Visualization

```bash
python visualize_simple.py
```

Generates:
- `EMERALDS.png` — Day 1 & Day 2 price charts
- `TOMATOES.png` — Day 1 & Day 2 price charts

---

## 📊 Performance Metrics

### Key Metrics to Track

- **PnL** — Profit and Loss
- **Sharpe Ratio** — Risk-adjusted returns
- **Max Drawdown** — Largest peak-to-trough decline
- **Fill Rate** — Percentage of orders executed
- **Position Utilization** — Average |position| / limit

### Validation Checks

✅ Fair value tracks market price  
✅ Spread capture is consistent  
✅ Position stays within limits  
✅ No runaway positions  
✅ Logger output is under 3750 chars

---

## 🚀 Improvements for Future Rounds

### Short Term
- [ ] Fine-tune EMA alpha parameter
- [ ] Optimize penny jumping offsets
- [ ] Add volatility-based position sizing

### Medium Term
- [ ] Implement order flow analysis
- [ ] Add pair trading strategies
- [ ] Develop basket arbitrage for multi-product rounds

### Long Term
- [ ] Options pricing and trading
- [ ] Statistical arbitrage patterns
- [ ] Machine learning for signal generation

---

## 📚 References

- **CMU Physics Team Strategy** — Prosperity 3 Winners
- **Chris Roberts (Princeton)** — Mean reversion analysis and wall mid validation
- **IMC Prosperity Documentation** — [prosperity.imc.com](https://prosperity.imc.com)

---

## 🤝 Team

- **[Nom 1]** — Strategy & Algorithm Development
- **[Nom 2]** — Data Analysis & Backtesting
- **[Nom 3]** — Implementation & Testing
- **[Nom 4]** — Documentation & Code Review

---

## 📝 License

This project is for educational purposes as part of the IMC Prosperity 4 competition.

---

## 🔗 Links

- **Competition:** [IMC Prosperity 4](https://prosperity.imc.com)
- **Team Dashboard:** [Link to your team page]
- **Documentation:** [Link to IMC docs]

---

**Last Updated:** March 2026  
**Status:** ✅ Tutorial Round Complete | 🚧 Round 1 In Progress
