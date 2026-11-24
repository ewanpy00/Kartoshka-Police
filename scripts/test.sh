#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

./scripts/env.sh

failed=0

run() {
  echo "== $1"
  shift
  "$@" || failed=1
}

run core docker compose -p kartoshka-police exec -T core pytest -q
run sandbox docker compose -p kartoshka-police exec -T -w /srv/sandbox sandbox pytest -q -p no:cacheprovider
run hunter docker compose -p kartoshka-police exec -T hunter pytest -q
run console sh -c "docker compose -p kartoshka-police exec -T console npm test && docker compose -p kartoshka-police exec -T console npm run build -- --outDir /tmp/console-dist --emptyOutDir"

if [ "$failed" -ne 0 ]; then
  echo "Some suites failed"
  exit 1
fi
echo "All suites passed"
