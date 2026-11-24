#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

read -r -p "This deletes all containers and volumes, including the database. Type yes to continue: " answer
if [ "$answer" != "yes" ]; then
  echo "Aborted"
  exit 1
fi
docker compose --profile stretch down -v --remove-orphans
