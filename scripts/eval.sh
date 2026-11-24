#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

docker compose exec -T -w /srv core python -m eval data/eval/sample.csv
