import pandas as pd
import matplotlib.pyplot as plt

# Load the data — semicolon separated
df = pd.read_csv("prices_round_0_day_-2.csv", sep=";")

# Split into separate dataframes per product
emeralds = df[df["product"] == "EMERALDS"].copy()
tomatoes = df[df["product"] == "TOMATOES"].copy()

# Create two separate subplots stacked vertically
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))
fig.suptitle("Prosperity 4 — Tutorial Round Data (Day -2)", fontsize=14, fontweight="bold")

# ── Emeralds ──────────────────────────────────────────────
ax1.plot(emeralds["timestamp"], emeralds["mid_price"], color="royalblue", linewidth=1.5, label="Mid Price")
ax1.plot(emeralds["timestamp"], emeralds["bid_price_1"], color="green", linewidth=0.8, alpha=0.5, linestyle="--", label="Best Bid")
ax1.plot(emeralds["timestamp"], emeralds["ask_price_1"], color="red", linewidth=0.8, alpha=0.5, linestyle="--", label="Best Ask")
ax1.set_title("EMERALDS", fontweight="bold")
ax1.set_ylabel("Price")
ax1.legend(loc="upper right")
ax1.grid(True, alpha=0.3)
# Set y-axis range tight around the actual prices so you can see any movement
emerald_mid = emeralds["mid_price"]
ax1.set_ylim(emerald_mid.min() - 20, emerald_mid.max() + 20)

# ── Tomatoes ──────────────────────────────────────────────
ax2.plot(tomatoes["timestamp"], tomatoes["mid_price"], color="tomato", linewidth=1.5, label="Mid Price")
ax2.plot(tomatoes["timestamp"], tomatoes["bid_price_1"], color="green", linewidth=0.8, alpha=0.5, linestyle="--", label="Best Bid")
ax2.plot(tomatoes["timestamp"], tomatoes["ask_price_1"], color="red", linewidth=0.8, alpha=0.5, linestyle="--", label="Best Ask")
ax2.set_title("TOMATOES", fontweight="bold")
ax2.set_xlabel("Timestamp")
ax2.set_ylabel("Price")
ax2.legend(loc="upper right")
ax2.grid(True, alpha=0.3)
tomato_mid = tomatoes["mid_price"]
ax2.set_ylim(tomato_mid.min() - 20, tomato_mid.max() + 20)

plt.tight_layout()
plt.show()

# ── Print quick stats ──────────────────────────────────────
print("=== EMERALDS ===")
print(f"  Mid price range: {emerald_mid.min():.1f} — {emerald_mid.max():.1f}")
print(f"  Std deviation:   {emerald_mid.std():.4f}")
print(f"  Mean:            {emerald_mid.mean():.2f}")

print("\n=== TOMATOES ===")
print(f"  Mid price range: {tomato_mid.min():.1f} — {tomato_mid.max():.1f}")
print(f"  Std deviation:   {tomato_mid.std():.4f}")
print(f"  Mean:            {tomato_mid.mean():.2f}")

