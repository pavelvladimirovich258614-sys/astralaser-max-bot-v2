Write-Host "=== HARNESS INIT (Astralaser v2) ==="
Write-Host "Working dir: $PWD"

Write-Host "`n[1/4] Architecture checks..."
$slot1 = Select-String -Path "src/bot/handlers/*.py" -Pattern "from src.db.crud" -List
if ($slot1) { Write-Host "VIOLATION: handlers import crud directly!" -ForegroundColor Red; exit 1 }
Write-Host "Architecture: OK"

Write-Host "`n[2/4] Running tests..."
python -m pytest -v --tb=short
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n[3/4] Lint..."
python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n[4/4] Type check..."
python -m mypy src/
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n=== READY ===" -ForegroundColor Green
