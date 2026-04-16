#!/usr/bin/env bash
# run_backtest.sh — Run prosperity4 backtester against submission.py for Round 1
#
# Usage:
#   bash scripts/run_backtest.sh             # all 3 days, merged PnL
#   bash scripts/run_backtest.sh --print     # stream trader stdout
#
# Requires: pip install prosperity4bt

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBMISSION="$ROOT/submission.py"
DATA_DIR="$ROOT/data"
LOG_DIR="$ROOT/backtests"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/run_$TIMESTAMP.log"

if [[ -x "$ROOT/../.venv/Scripts/python.exe" ]]; then
    PYTHON_BIN="$ROOT/../.venv/Scripts/python.exe"
elif [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
    PYTHON_BIN="$ROOT/.venv/Scripts/python.exe"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
else
    echo "ERROR: python executable not found in PATH"
    exit 1
fi

mkdir -p "$LOG_DIR"

# Resolve the backtester command. Prefer module invocation because it works
# even when the console-script shim is missing from PATH.
if "$PYTHON_BIN" -c "import prosperity4bt" &>/dev/null; then
    BACKTEST_MODE="prosperity4bt-module"
    BACKTEST_CMD=("$PYTHON_BIN" -m prosperity4bt)
elif command -v prosperity4bt &>/dev/null; then
    BACKTEST_MODE="cli"
    BACKTEST_CMD=(prosperity4bt)
elif command -v prosperity4btest &>/dev/null; then
    BACKTEST_MODE="cli"
    BACKTEST_CMD=(prosperity4btest)
else
    echo "ERROR: backtester not found. Install with: pip install prosperity4bt"
    exit 1
fi

echo "Submission : $SUBMISSION"
echo "Data       : $DATA_DIR"
echo "Log        : $LOG_FILE"
echo "Backtester : ${BACKTEST_CMD[*]}"
echo ""

echo "Running backtest (Round 1, days -2 / -1 / 0)..."
if [[ "${BACKTEST_MODE:-}" == "prosperity4bt-module" ]]; then
    # Work around prosperity4bt's static LIMITS map by adding products seen in
    # the provided dataset. This prevents KeyError for custom product names.
    "$PYTHON_BIN" - "$SUBMISSION" 1--2 1--1 1-0 \
        --merge-pnl \
        --data "$DATA_DIR" \
        --out "$LOG_FILE" \
        "$@" <<'PY'
import csv
import sys
from pathlib import Path

import prosperity4bt.data as data_mod
import prosperity4bt.runner as runner_mod
from prosperity4bt.__main__ import app

args = sys.argv[1:]
if "--vis" in args:
    print("Warning: --vis is not supported by prosperity4bt and will be ignored")
    args = [a for a in args if a != "--vis"]

data_root = None
for i, arg in enumerate(args):
    if arg == "--data" and i + 1 < len(args):
        data_root = Path(args[i + 1])
        break

if data_root is not None and data_root.exists():
    products = set()
    for prices_path in data_root.glob("round*/prices_round_*_day_*.csv"):
        with prices_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                product = row.get("product")
                if product:
                    products.add(product)

    for product in products:
        data_mod.LIMITS.setdefault(product, 20)
        runner_mod.LIMITS.setdefault(product, 20)

sys.argv = ["prosperity4bt", *args]
app()
PY
else
    "${BACKTEST_CMD[@]}" "$SUBMISSION" 1--2 1--1 1-0 \
        --merge-pnl \
        --data "$DATA_DIR" \
        --out "$LOG_FILE" \
        "$@"
fi

echo ""
echo "Done. Log saved to $LOG_FILE"
