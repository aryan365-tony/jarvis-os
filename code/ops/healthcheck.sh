#!/usr/bin/env bash
set -euo pipefail
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8080/health >/dev/null; then
    exit 0
  fi
  sleep 1
done
echo "llama-server did not become healthy in time" >&2
exit 1
