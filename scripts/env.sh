#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ -f .env ]; then
  exit 0
fi

token=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
adguard=$(head -c 18 /dev/urandom | od -An -tx1 | tr -d ' \n')
while IFS= read -r line; do
  if [ "$line" = "CORE_WRITE_TOKEN=" ]; then
    line="CORE_WRITE_TOKEN=$token"
  elif [ "$line" = "ADGUARD_PASSWORD=" ]; then
    line="ADGUARD_PASSWORD=$adguard"
  fi
  printf '%s\n' "$line"
done < .env.example > .env
echo "Created .env with a generated CORE_WRITE_TOKEN and ADGUARD_PASSWORD"
