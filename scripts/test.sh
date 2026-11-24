#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

failed=0

run() {
  echo "== $1"
  shift
  "$@" || failed=1
}

run core docker compose exec -T core pytest -q
run sandbox docker compose exec -T -w /srv/sandbox sandbox pytest -q -p no:cacheprovider
run hunter docker compose exec -T hunter pytest -q
run console docker compose exec -T console npm run build

if [ "$failed" -ne 0 ]; then
  echo "Some suites failed"
  exit 1
fi
echo "All suites passed"
