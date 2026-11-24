#!/usr/bin/env bash
# Runs the eval on the development set and on the hold-out set. Pass a CSV to run only that one.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/lib.sh

./scripts/env.sh

sets=("$@")
[ ${#sets[@]} -eq 0 ] && sets=(data/eval/test.csv data/eval/holdout.csv)
for set in "${sets[@]}"; do
  echo "== ${set}"
  "${COMPOSE[@]}" exec -T -w /srv core python -m eval "${set}"
done
