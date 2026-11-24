#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# An existing .env is never changed. Only name the keys a pull added to .env.example.
if [ -f .env ]; then
  missing=$(comm -23 \
    <(sed -n 's/^\([A-Z][A-Z0-9_]*\)=.*/\1/p' .env.example | sort -u) \
    <(sed -n 's/^\([A-Z][A-Z0-9_]*\)=.*/\1/p' .env | sort -u) | tr '\n' ' ')
  if [ -n "${missing% }" ]; then
    echo "Keys in .env.example but not in .env (add the ones you need): ${missing% }" >&2
  fi
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
