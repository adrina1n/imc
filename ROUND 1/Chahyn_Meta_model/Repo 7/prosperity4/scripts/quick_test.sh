#!/usr/bin/env bash
# quick_test.sh — Syntax-check submission.py and run a smoke test.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBMISSION="$ROOT/submission.py"

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

# Python on Windows expects a Windows-style path when called from Git Bash.
if command -v cygpath &>/dev/null; then
	SUBMISSION_PY_PATH="$(cygpath -w "$SUBMISSION")"
else
	SUBMISSION_PY_PATH="$SUBMISSION"
fi

echo "Building submission..."
"$PYTHON_BIN" "$ROOT/tools/build_submission.py"

echo "Syntax check..."
"$PYTHON_BIN" -m py_compile "$SUBMISSION_PY_PATH" && echo "OK"

echo "Import check..."
SUBMISSION_IMPORT_PATH="$SUBMISSION_PY_PATH" "$PYTHON_BIN" -c "import importlib.util, os, sys
spec = importlib.util.spec_from_file_location('submission', os.environ['SUBMISSION_IMPORT_PATH'])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
t = mod.Trader()
print('Trader instantiated OK')
"

echo "All checks passed."
