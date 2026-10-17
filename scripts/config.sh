#!/usr/bin/env bash
# Shared helpers. Usage in scripts:  source config.sh <env>   (env = dev | prod, default dev)
set -euo pipefail
export ENVIRONMENT="${1:-${ENVIRONMENT:-dev}}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export STACK_NAME="books-api-${ENVIRONMENT}"
export AWS_PAGER=""
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

stack_output() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
api_key() {
  aws apigateway get-api-key --api-key "$(stack_output ApiKeyId)" --include-value \
    --query value --output text --region "$AWS_REGION"
}
