#!/usr/bin/env python3
"""
param_sweep.py — Grid search over strategy parameters using the backtester.

Usage:
    python tools/param_sweep.py
"""

import itertools
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Define your parameter grid here
PARAM_GRID = {
    "half_spread": [1, 2, 3],
    "ema_alpha": [0.1, 0.2, 0.3],
}


def run_backtest(params: dict) -> float:
    """Run a single backtest and return the final PnL."""
    # Adjust this command to match your backtester CLI
    cmd = ["python", "-m", "prosperity4bt", str(ROOT / "submission.py"), "--params", json.dumps(params)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print(f"Backtest failed for {params}:\n{result.stderr}")
        return float("-inf")
    # Parse PnL from stdout — adjust to match your backtester output format
    for line in result.stdout.splitlines():
        if "Total PnL" in line:
            return float(line.split(":")[-1].strip())
    return float("-inf")


def sweep():
    keys = list(PARAM_GRID.keys())
    values = list(PARAM_GRID.values())
    best_pnl = float("-inf")
    best_params = None

    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        pnl = run_backtest(params)
        print(f"{params} -> PnL: {pnl:.2f}")
        if pnl > best_pnl:
            best_pnl = pnl
            best_params = params

    print(f"\nBest params: {best_params}  (PnL: {best_pnl:.2f})")


if __name__ == "__main__":
    sweep()
