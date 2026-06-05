#!/usr/bin/env bash
set -euo pipefail

cd "${FOOOCUS_HOME:-/opt/fooocus}"

mkdir -p models/checkpoints models/loras models/vae models/embeddings models/inpaint outputs

PORT="${FOOOCUS_PORT:-7865}"
LISTEN="${FOOOCUS_LISTEN:-0.0.0.0}"
EXTRA_ARGS="${FOOOCUS_ARGS:---preset realistic}"

exec /opt/fooocus-venv/bin/python entry_with_update.py \
  --listen "${LISTEN}" \
  --port "${PORT}" \
  ${EXTRA_ARGS}
