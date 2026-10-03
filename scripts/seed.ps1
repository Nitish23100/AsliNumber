# Seed demo tenants and users against the configured MONGO_URI.
Set-Location "$PSScriptRoot\..\backend"
python -m app.cli seed --demo
Set-Location $PSScriptRoot