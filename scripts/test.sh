#!/usr/bin/env bash
# Run backend and frontend test suites.
set -euo pipefail
cd "$(dirname "$0")/../backend"
python -m pytest -q
cd "$(dirname "$0")/../frontend"
npm run typecheck
npm run test