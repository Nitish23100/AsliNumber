# Run backend and frontend test suites.
Set-Location "$PSScriptRoot\..\backend"
python -m pytest -q
Set-Location "$PSScriptRoot\..\frontend"
npm run typecheck
npm run test
Set-Location $PSScriptRoot