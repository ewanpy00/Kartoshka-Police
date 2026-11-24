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

run core docker compose exec -T core pytest -q
run sandbox docker compose exec -T -w /srv/sandbox sandbox pytest -q -p no:cacheprovider
run hunter docker compose exec -T hunter pytest -q
run console docker compose exec -T console npm run build -- --outDir /tmp/console-dist --emptyOutDir
run resident docker compose exec -T resident npm run build -- --outDir /tmp/resident-dist --emptyOutDir
run dns docker compose --profile stretch run --rm --no-deps dnssync python -m pytest -q -p no:cacheprovider
run gatekeeper docker run --rm -v "$PWD/gatekeeper":/gk -v kp-gradle-cache:/home/gradle/.gradle -w /gk/logic-test \
  gradle:8.11.1-jdk17 gradle test --no-daemon -q

if [ "$failed" -ne 0 ]; then
  echo "Some suites failed"
  exit 1
fi
echo "All suites passed"
