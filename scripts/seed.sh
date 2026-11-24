#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/lib.sh

./scripts/env.sh

"${COMPOSE[@]}" exec -T core python -m app.seed
