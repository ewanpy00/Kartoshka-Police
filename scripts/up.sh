#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

./scripts/env.sh

if [ "${1:-}" = "stretch" ]; then
  docker compose -p kartoshka-police --profile stretch up -d --build --renew-anon-volumes --wait
else
  docker compose -p kartoshka-police up -d --build --renew-anon-volumes --wait
fi
