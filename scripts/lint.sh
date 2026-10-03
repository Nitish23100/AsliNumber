#!/usr/bin/env bash
# Lint and format-check both backend and frontend.
set -euo pipefail
cd "$(dirname "$0")/../backend"
python -m ruff check .
python -m ruff format --check .
cd "$(dirname "$0")/../frontend"
npm run lint
npm run format:check