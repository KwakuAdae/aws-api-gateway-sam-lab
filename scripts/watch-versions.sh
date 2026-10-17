#!/usr/bin/env bash
# During a canary/linear deployment, call the API repeatedly and count which Lambda version
# answered each request:  ./scripts/watch-versions.sh prod [requests]
source "$(dirname "$0")/config.sh" "${1:-prod}"

API_URL="$(stack_output ApiUrl)"
API_KEY="$(api_key)"
COUNT="${2:-40}"

echo ">> Sending ${COUNT} requests to ${API_URL}/books ..."
for _ in $(seq "$COUNT"); do
  curl -s -D - -o /dev/null -H "x-api-key: ${API_KEY}" "${API_URL}/books" \
    | grep -i '^x-served-by' | python3 -c 'import json,sys; print("version", json.loads(sys.stdin.read().split(":",1)[1])["lambdaVersion"])'
  sleep 0.2
done | sort | uniq -c
