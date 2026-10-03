#!/usr/bin/env bash
# Install backend and frontend dependencies.
set -euo pipefail
cd "$(dirname "$0")/../backend"
pip install -e ".[dev]"
cd "$(dirname "$0")/../frontend"
npm install