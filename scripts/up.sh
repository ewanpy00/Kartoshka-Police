#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/lib.sh

./scripts/env.sh

if [ "${1:-}" = "stretch" ]; then
  "${COMPOSE[@]}" --profile stretch up -d --build --renew-anon-volumes --wait
else
  "${COMPOSE[@]}" up -d --build --renew-anon-volumes --wait
fi
