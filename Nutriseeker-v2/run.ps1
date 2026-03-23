# Run NutriSeeker from project root (same folder as this script).
$env:PYTHONPATH = $PSScriptRoot
Write-Host "PYTHONPATH=$env:PYTHONPATH"
uvicorn nutriseeker.app.main:app --reload --host 127.0.0.1 --port 8000
