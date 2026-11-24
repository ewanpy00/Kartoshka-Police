#!/usr/bin/env bash
# Supervisor for the single Railway service: core, RQ worker, sandbox and optionally hunter in one container.
# Runs as root under tini only to drop privileges; nothing here prints a variable's value.
set -euo pipefail

missing=0
for name in DATABASE_URL REDIS_URL CORE_WRITE_TOKEN; do
  if [ -z "${!name:-}" ]; then
    echo "start: required variable $name is not set" >&2
    missing=1
  fi
done
[ "$missing" -eq 0 ] || exit 1
if [ "${#CORE_WRITE_TOKEN}" -lt 32 ]; then
  echo "start: CORE_WRITE_TOKEN must be at least 32 characters" >&2
  exit 1
fi

PORT="${PORT:-8000}"
export PORT
# rq reads its Redis URL from this variable, so it never appears in a command line other users can read.
export RQ_REDIS_URL="$REDIS_URL"
HUNTER_ENABLED="${HUNTER_ENABLED:-false}"
HUNTER_SOURCES="${HUNTER_SOURCES:-feeds,nrd,watchlist}"
if [ "$HUNTER_ENABLED" = "true" ]; then
  case ",$HUNTER_SOURCES," in
    *,ct,*)
      echo "start: HUNTER_SOURCES must not contain ct, certstream is not part of this image" >&2
      exit 1
      ;;
  esac
fi

as_core=(setpriv --reuid=core --regid=core --init-groups env HOME=/home/core)

cd /srv/core
"${as_core[@]}" /opt/core/bin/alembic upgrade head
"${as_core[@]}" /opt/core/bin/python -m app.seed

declare -A names=()
pids=()

start() {
  local name="$1"
  shift
  "$@" &
  names[$!]="$name"
  pids+=("$!")
}

stop_all() {
  kill -TERM "${pids[@]}" 2>/dev/null || true
  wait 2>/dev/null || true
}

trap 'stop_all; exit 0' TERM INT

sandbox_home="$(mktemp -d /tmp/sandbox-home.XXXXXX)"
chown pwuser:pwuser "$sandbox_home"
chmod 700 "$sandbox_home"

cd /srv/sandbox
start sandbox env -i \
  PATH=/opt/sandbox/bin:/usr/local/bin:/usr/bin:/bin \
  HOME="$sandbox_home" \
  CAPTURES_DIR="${CAPTURES_DIR:-/captures}" \
  CAPTURE_TIMEOUT_MS="${CAPTURE_TIMEOUT_MS:-15000}" \
  PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}" \
  setpriv --reuid=pwuser --regid=pwuser --init-groups \
  /opt/sandbox/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001

cd /srv/core
start core "${as_core[@]}" /opt/core/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
start worker "${as_core[@]}" /opt/core/bin/rq worker "${RQ_QUEUE:-deep}"

if [ "$HUNTER_ENABLED" = "true" ]; then
  cd /srv/hunter
  start hunter "${as_core[@]}" env \
    HUNTER_SOURCES="$HUNTER_SOURCES" \
    CORE_URL="http://127.0.0.1:$PORT" \
    HUNTER_SUBMIT_PER_MINUTE="${HUNTER_SUBMIT_PER_MINUTE:-20}" \
    /opt/hunter/bin/python -m app.certstream_consumer
fi

finished=""
wait -n -p finished "${pids[@]}" || true
echo "start: ${names[$finished]:-a child} exited, stopping the rest" >&2
stop_all
exit 1
