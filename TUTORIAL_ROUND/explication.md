# Tutorial Round Trading Strategy

## Overview

For the tutorial round, we implement a simple but robust market making strategy based on four core components:

1. Fair price estimation
2. Market making (spread capture)
3. Position management
4. Order flow / trader following

The objective is to balance profitability and risk control while maintaining consistent execution in the order book.

---

## 1. Fair Price Estimation

We define a fair price as our estimate of the true value of the asset.

For simple products, we use:

* Mid-price:

  fair_price = (best_bid + best_ask) / 2

This serves as the reference point for all trading decisions.

---

## 2. Market Making (Spread Capture)

We continuously place buy and sell orders around the fair price:

* Buy below fair value
* Sell above fair value

This allows us to capture the bid-ask spread when both orders are executed.

To improve execution, we use **penny jumping**:

* bid = best_bid + 1
* ask = best_ask - 1

But only if the price remains profitable relative to the fair price.

---

## 3. Position Management (Inventory Control)

We track our position at all times:

* Positive position (long) → exposed to price decreases
* Negative position (short) → exposed to price increases

When our exposure becomes too large, we reduce it even if no profit is available.

Example:

* If short → we buy at fair value
* If long → we sell at fair value

This reduces risk and stabilizes the strategy.

---

## 4. Order Flow / Trader Following

We monitor market trades to detect the behavior of other participants.

If a specific trader consistently buys or sells, we interpret this as a potential signal.

Example:

* If a trader repeatedly buys → possible upward pressure
* If a trader repeatedly sells → possible downward pressure

We can then adapt our behavior:

* Follow the direction (momentum)
* Or adjust our quotes more aggressively

This adds a simple form of signal-based trading on top of market making.

---

## Conclusion

This strategy combines:

* Pricing (fair value)
* Execution (penny jumping)
* Risk management (position control)
* Signal extraction (order flow)

While simple, this framework provides a strong baseline for more advanced strategies.
