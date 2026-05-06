#!/bin/bash
set -e

echo "=== HARNESS INIT (Astralaser v2) ==="
echo "Working dir: $(pwd)"

echo ""
echo "[1/4] Architecture checks..."
if grep -r "from src.db.crud" src/bot/handlers/*.py 2>/dev/null; then
    echo "VIOLATION: handlers import crud directly!"
    exit 1
fi
echo "Architecture: OK"

echo ""
echo "[2/4] Running tests..."
python -m pytest -v --tb=short

echo ""
echo "[3/4] Lint..."
python -m ruff check .

echo ""
echo "[4/4] Type check..."
python -m mypy src/

echo ""
echo "=== READY ==="
