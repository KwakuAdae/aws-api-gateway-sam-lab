#!/usr/bin/env bash
# Delete one environment's stack:  ./scripts/cleanup.sh dev   (then ./scripts/cleanup.sh prod)
source "$(dirname "$0")/config.sh" "${1:-dev}"
sam delete --stack-name "$STACK_NAME" --region "$AWS_REGION" --no-prompts
echo "✅ ${STACK_NAME} deleted"
