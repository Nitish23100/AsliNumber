# Lint and format-check both backend and frontend.
Set-Location "$PSScriptRoot\..\backend"
python -m ruff check .
python -m ruff format --check .
Set-Location "$PSScriptRoot\..\frontend"
npm run lint
npm run format:check
Set-Location $PSScriptRoot