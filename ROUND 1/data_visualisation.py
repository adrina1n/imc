import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ── Chargement des 3 jours ──────────────────────────────────────────────────
day_m2 = pd.read_csv('data_R1/prices_round_1_day_-2.csv', sep=';')
day_m1 = pd.read_csv('data_R1/prices_round_1_day_-1.csv', sep=';')
day_0  = pd.read_csv('data_R1/prices_round_1_day_0.csv',  sep=';')

for df in [day_m2, day_m1, day_0]:
    df.drop(df[df['mid_price'] == 0].index, inplace=True)

DAYS     = [day_m2, day_m1, day_0]
LABELS   = ['Day -2 (tutorial)', 'Day -1 (tutorial)', 'Day 0 (compétition)']
PRODUCTS = ['ASH_COATED_OSMIUM', 'INTARIAN_PEPPER_ROOT']


# ── Wall Mid ────────────────────────────────────────────────────────────────
# Pour chaque timestamp : bid avec le plus gros volume / ask avec le plus gros volume
# Beaucoup plus stable que le BBO mid car les petits ordres éphémères sont ignorés
def compute_wall_mid(d: pd.DataFrame) -> pd.Series:
    def row_wm(row):
        bids = [(row[f'bid_price_{i}'], row[f'bid_volume_{i}'])
                for i in [1, 2, 3]
                if pd.notna(row.get(f'bid_price_{i}')) and pd.notna(row.get(f'bid_volume_{i}'))]
        asks = [(row[f'ask_price_{i}'], row[f'ask_volume_{i}'])
                for i in [1, 2, 3]
                if pd.notna(row.get(f'ask_price_{i}')) and pd.notna(row.get(f'ask_volume_{i}'))]
        if not bids or not asks:
            return np.nan
        wall_bid = max(bids, key=lambda x: x[1])[0]  # bid au plus gros volume
        wall_ask = max(asks, key=lambda x: x[1])[0]  # ask au plus gros volume
        return (wall_bid + wall_ask) / 2
    return d.apply(row_wm, axis=1)


def plot_product(product_name, days, labels):
    show_wall_mid = (product_name == 'ASH_COATED_OSMIUM')

    fig, axes = plt.subplots(1, 3, figsize=(24, 6))

    for ax, df, label in zip(axes, days, labels):
        d = df[df['product'] == product_name].copy().sort_values('timestamp')

        # BBO mid
        ax.plot(d['timestamp'], d['mid_price'],
                color='#2196F3', linewidth=1.2, label='BBO Mid', alpha=0.85)

        # Wall Mid (ASH uniquement)
        if show_wall_mid:
            wm = compute_wall_mid(d)
            ax.plot(d['timestamp'], wm,
                    color='#FF9800', linewidth=1.0, linestyle='--',
                    label='Wall Mid', alpha=0.9)
            wm_std  = wm.dropna().std()
            bbo_std = d['mid_price'].std()
            noise_reduction = (1 - wm_std / bbo_std) * 100

        low    = d['mid_price'].min()
        high   = d['mid_price'].max()
        spread = (d['ask_price_1'] - d['bid_price_1']).mean()
        std    = d['mid_price'].std()

        stats = (
            f"Low:        {low:,.1f}\n"
            f"High:       {high:,.1f}\n"
            f"Range:      {high - low:,.1f}\n"
            f"BBO std:    {std:.2f}\n"
            f"Avg Spread: {spread:.2f}"
        )
        if show_wall_mid:
            stats += f"\nWall std:   {wm_std:.2f}\nBruit -:    {noise_reduction:.0f}%"

        ax.text(0.02, 0.98, stats, transform=ax.transAxes,
                va='top', ha='left', fontsize=9, family='monospace',
                bbox=dict(boxstyle='round', alpha=0.1))

        ax.set_title(label, fontsize=14)
        ax.set_xlabel('Timestamp')
        ax.set_ylabel('Prix')
        ax.legend(fontsize=9, loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.ticklabel_format(style='plain', axis='x')

    fig.suptitle(product_name, fontsize=20, fontweight='bold')
    plt.tight_layout()
    plt.show()

    # Résumé console
    print(f"\n{'─'*60}")
    print(f"{product_name}")
    print(f"{'─'*60}")
    for df, label in zip(days, labels):
        d = df[df['product'] == product_name]
        low    = d['mid_price'].min()
        high   = d['mid_price'].max()
        spread = (d['ask_price_1'] - d['bid_price_1']).mean()
        std    = d['mid_price'].std()
        line   = (f"{label:<25}  Low={low:>8.1f}  High={high:>8.1f}  "
                  f"Range={high-low:>6.1f}  Std={std:>6.2f}  Spread={spread:.2f}")
        if show_wall_mid:
            wm = compute_wall_mid(d.sort_values('timestamp'))
            line += f"  WallStd={wm.dropna().std():.2f}"
        print(line)


for product in PRODUCTS:
    plot_product(product, DAYS, LABELS)
