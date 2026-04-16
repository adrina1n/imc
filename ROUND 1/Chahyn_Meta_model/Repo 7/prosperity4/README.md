# Prosperity 4

IMC Prosperity 4 trading competition workspace.

## Structure

| Path | Purpose |
|------|---------|
| `submission.py` | Upload this file to the competition |
| `datamodel.py` | Official datamodel (keep in sync with the wiki) |
| `strategies/` | Modular, testable strategy classes |
| `analysis/` | Jupyter notebooks for EDA per round |
| `data/` | Raw CSV data from the competition |
| `backtester/` | Local copy of `prosperity4bt` |
| `backtests/` | Output logs from backtester runs |
| `tools/` | Build, sweep, and visualisation utilities |
| `scripts/` | Shell scripts for common workflows |

## Quickstart

```bash
# Install deps
pip install prosperity4bt matplotlib pandas jupyter

# Syntax + import check
bash scripts/quick_test.sh

# Full backtest (auto-builds submission.py first)
bash scripts/run_backtest.sh

# Parameter sweep
python tools/param_sweep.py

# Visualise results
python tools/dashboard.py --prices data/round1/prices_round_1_day_0.csv
python tools/dashboard.py --log backtests/run_<timestamp>.log
```

## Workflow

1. Develop strategy logic in `strategies/`
2. Wire it up in `submission.py` (or let `tools/build_submission.py` do it)
3. Run `quick_test.sh` to catch syntax errors fast
4. Run `run_backtest.sh` to get PnL numbers
5. Iterate with `param_sweep.py` to tune parameters
6. Submit `submission.py` to the competition platform
