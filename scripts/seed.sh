#!/usr/bin/env bash
# Seed demo tenants and users against the configured MONGO_URI.
set -euo pipefail
cd "$(dirname "$0")/../backend"
python -m app.cli seed --demo