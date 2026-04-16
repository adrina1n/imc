#!/usr/bin/env python3
"""
dashboard.py — Visualisation tools for backtest logs and price data.

Usage:
    python tools/dashboard.py --log backtests/run_001.log
"""

import argparse
import csv
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import pandas as pd
except ImportError:
    raise SystemExit("Install matplotlib and pandas: pip install matplotlib pandas")

ROOT = Path(__file__).parent.parent


def plot_prices(csv_path: Path):
    df = pd.read_csv(csv_path, sep=";")
    products = df["product"].unique() if "product" in df.columns else []
    fig, axes = plt.subplots(len(products), 1, figsize=(12, 4 * len(products)), squeeze=False)
    for ax, product in zip(axes[:, 0], products):
        sub = df[df["product"] == product]
        ax.plot(sub["timestamp"], sub["mid_price"], label="mid")
        ax.set_title(product)
        ax.legend()
    plt.tight_layout()
    plt.show()


def plot_pnl(log_path: Path):
    timestamps, pnls = [], []
    with open(log_path) as f:
        for line in f:
            if "PnL" in line:
                parts = line.split()
                try:
                    timestamps.append(int(parts[0]))
                    pnls.append(float(parts[-1]))
                except (ValueError, IndexError):
                    continue
    plt.figure(figsize=(12, 4))
    plt.plot(timestamps, pnls)
    plt.title("Cumulative PnL")
    plt.xlabel("Timestamp")
    plt.ylabel("PnL")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", type=Path, help="Path to prices CSV")
    parser.add_argument("--log", type=Path, help="Path to backtest log")
    args = parser.parse_args()

    if args.prices:
        plot_prices(args.prices)
    if args.log:
        plot_pnl(args.log)
