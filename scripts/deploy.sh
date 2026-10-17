#!/usr/bin/env bash
# Build and deploy one environment:  ./scripts/deploy.sh dev   |   ./scripts/deploy.sh prod
source "$(dirname "$0")/config.sh" "${1:-dev}"
cd "$ROOT_DIR"

sam validate --lint
sam build
sam deploy --config-env "$ENVIRONMENT" --no-fail-on-empty-changeset

echo ""
echo "✅ ${ENVIRONMENT} deployed"
echo "   export API_URL=$(stack_output ApiUrl)"
echo "   export API_KEY=$(api_key)"
