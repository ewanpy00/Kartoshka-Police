#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/lib.sh

./scripts/env.sh

failed=0

run() {
  echo "== $1"
  shift
  "$@" || failed=1
}

# Unit tests first, then the production build.
console_suite() {
  "${COMPOSE[@]}" exec -T console npm test &&
    "${COMPOSE[@]}" exec -T console npm run build -- --outDir /tmp/console-dist --emptyOutDir
}

run core "${COMPOSE[@]}" exec -T core pytest -q
run sandbox "${COMPOSE[@]}" exec -T -w /srv/sandbox sandbox pytest -q -p no:cacheprovider
run hunter "${COMPOSE[@]}" exec -T hunter pytest -q
run console console_suite
run resident "${COMPOSE[@]}" exec -T resident npm run build -- --outDir /tmp/resident-dist --emptyOutDir
run dns "${COMPOSE[@]}" --profile stretch run --rm --no-deps dnssync python -m pytest -q -p no:cacheprovider
run gatekeeper docker run --rm -v "$PWD/gatekeeper":/gk -v kp-gradle-cache:/home/gradle/.gradle -w /gk/logic-test \
  gradle:8.11.1-jdk17 gradle test --no-daemon -q

if [ "$failed" -ne 0 ]; then
  echo "Some suites failed"
  exit 1
fi
echo "All suites passed"
