#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/lib.sh

./scripts/env.sh

# Only this project's containers, volumes and networks: the project name is fixed in COMPOSE.
read -r -p "This deletes all containers and volumes, including the database. Type yes to continue: " answer
if [ "$answer" != "yes" ]; then
  echo "Aborted"
  exit 1
fi
"${COMPOSE[@]}" --profile stretch down -v --remove-orphans
