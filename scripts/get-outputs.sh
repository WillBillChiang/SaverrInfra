#!/bin/bash

# Saverr API - Get Stack Outputs
# Usage: ./scripts/get-outputs.sh [environment]

set -e

ENVIRONMENT=${1:-dev}

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Error: Invalid environment. Use: dev, staging, or prod"
    exit 1
fi

STACK_NAME="saverr-api-$ENVIRONMENT"

echo "============================================"
echo "Stack Outputs: $STACK_NAME"
echo "============================================"

# Check if stack exists
if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" &> /dev/null; then
    echo "Error: Stack $STACK_NAME does not exist"
    exit 1
fi

# Get all outputs
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' \
    --output table

echo ""
echo "JSON format:"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs' \
    --output json
