#!/usr/bin/env bash
# Exercise every route of one environment:  ./scripts/test-api.sh dev
source "$(dirname "$0")/config.sh" "${1:-dev}"

API_URL="$(stack_output ApiUrl)"
API_KEY="$(api_key)"
K=(-H "x-api-key: ${API_KEY}")
J=(-H "Content-Type: application/json")
show() { echo ""; echo "── $1"; }

show "GET /health (MOCK integration: answered by API Gateway, no Lambda, no key)"
curl -s "${API_URL}/health"; echo

show "GET /books without an API key (expect 403)"
curl -s "${API_URL}/books" -w "  HTTP %{http_code}\n"

show "GET /nope (custom MISSING_AUTHENTICATION_TOKEN response, expect 404)"
curl -s "${API_URL}/nope" -w "  HTTP %{http_code}\n"

show "POST /books (expect 201)"
NEW=$(curl -s "${K[@]}" "${J[@]}" -X POST "${API_URL}/books" \
  -d '{"title":"Things Fall Apart","author":"Chinua Achebe","year":1958}')
echo "$NEW"
ID=$(echo "$NEW" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

show "POST /books with a bad body (rejected by the OpenAPI model before Lambda runs: 400)"
curl -s "${K[@]}" "${J[@]}" -X POST "${API_URL}/books" \
  -d '{"title":"","year":"soon","isbn":"x"}' -w "  HTTP %{http_code}\n"

show "GET /books?author=Chinua%20Achebe"
curl -s "${K[@]}" "${API_URL}/books?author=Chinua%20Achebe"; echo

show "PUT /books/${ID}"
curl -s "${K[@]}" "${J[@]}" -X PUT "${API_URL}/books/${ID}" -d '{"year":1959}'; echo

show "DELETE /books/${ID} (expect 204)"
curl -s -o /dev/null "${K[@]}" -X DELETE "${API_URL}/books/${ID}" -w "HTTP %{http_code}\n"

show "Which Lambda version answered? (X-Served-By header)"
curl -s -D - -o /dev/null "${K[@]}" "${API_URL}/books" | grep -i x-served-by || true
