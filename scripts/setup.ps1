# Install backend and frontend dependencies.
Set-Location "$PSScriptRoot\..\backend"
pip install -e ".[dev]"
Set-Location "$PSScriptRoot\..\frontend"
npm install
Set-Location $PSScriptRoot