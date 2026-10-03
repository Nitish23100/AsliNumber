#!/usr/bin/env bash
# Start the local Docker Compose stack.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up --build