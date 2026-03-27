#!/usr/bin/env bash

set -euo pipefail

MODEL="${MODEL:-MiniMax-M2.5}"
BASE_URL="${BASE_URL:-https://api.minimaxi.com/v1}"
API_KEY_ENV="${API_KEY_ENV:-MINIMAX_API_KEY}"
PROMPT="${PROMPT:-Reply with exactly: pong}"
MAX_TOKENS="${MAX_TOKENS:-8}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 127
fi

API_KEY="${!API_KEY_ENV:-}"
if [[ -z "${API_KEY}" ]]; then
  echo "Environment variable ${API_KEY_ENV} is not set." >&2
  exit 2
fi

URL="${BASE_URL%/}/chat/completions"
PAYLOAD="$(printf '{"model":"%s","messages":[{"role":"user","content":"%s"}],"max_tokens":%s}' \
  "${MODEL}" \
  "${PROMPT}" \
  "${MAX_TOKENS}")"

echo "POST ${URL}"
echo "model=${MODEL}"
echo "api_key_env=${API_KEY_ENV}"
echo

curl -sS -i "${URL}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  --data-binary "${PAYLOAD}"
