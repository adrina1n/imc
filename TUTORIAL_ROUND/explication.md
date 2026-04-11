# IMC Prosperity 4 - Tutorial Round Strategy

**Round:** Tutorial (Round 0)  
**Products:** EMERALDS, TOMATOES

---

##  Overview

This repository contains our algorithmic trading strategy for the **IMC Prosperity 4 Tutorial Round**. The strategy implements a robust market making approach with product-specific fair value estimation and risk management.

### Core Components

1. **Fair Price Estimation** — Product-specific valuation methods
2. **Market Making** — Spread capture via penny jumping
3. **Position Management** — Risk control with conditional trading
4. **Order Flow Analysis** — [Future enhancement]

**Objective:** Balance profitability and risk control while maintaining consistent execution in the order book.

---

##  Strategy Details

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
```

**Why Wall Mid?**
- BBO (best bid/offer) is noisy due to ephemeral small orders
- Deepest levels (highest volume) represent true liquidity
- Reduces noise by **~50%** (σ: 1.34 → 0.67)
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

 Always takes trades with an edge (price ≠ fair value)  
 Only takes fair-value trades that reduce exposure  
 Prevents accumulating dangerous positions  

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

