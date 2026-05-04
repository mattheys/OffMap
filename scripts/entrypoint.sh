#!/usr/bin/env bash
set -euo pipefail

mkdir -p /data/planet /data/tiles /data/search /data/state

if [[ "${STARTUP_IMPORT:-true}" == "true" ]]; then
  python3 -m offmap.pipeline
fi

if [[ "${AUTO_UPDATE:-true}" == "true" ]]; then
  cat >/tmp/offmap.cron <<EOF
${UPDATE_CRON:-0 3 1 * *} python3 -m offmap.pipeline
EOF
  supercronic /tmp/offmap.cron &
fi

exec uvicorn offmap.server:app --host 0.0.0.0 --port 8080
