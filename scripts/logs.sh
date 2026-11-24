#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

./scripts/env.sh

docker compose -p kartoshka-police --profile stretch logs -f --tail=100 "$@"
