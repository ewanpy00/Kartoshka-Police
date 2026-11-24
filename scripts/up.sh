#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

./scripts/env.sh

if [ "${1:-}" = "stretch" ]; then
  docker compose --profile stretch up -d --build --renew-anon-volumes --wait
else
  docker compose up -d --build --renew-anon-volumes --wait
fi
