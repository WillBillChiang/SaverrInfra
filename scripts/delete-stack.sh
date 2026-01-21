#!/bin/bash

# Saverr API - Delete Stack Script
# Usage: ./scripts/delete-stack.sh [environment]
# 
# WARNING: This will delete all resources including DynamoDB tables!

set -e

ENVIRONMENT=${1:-}
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -z "$ENVIRONMENT" ]; then
    echo "Usage: ./scripts/delete-stack.sh [environment]"
    echo "Environments: dev, staging, prod"
    exit 1
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Error: Invalid environment. Use: dev, staging, or prod"
    exit 1
fi

STACK_NAME="saverr-api-$ENVIRONMENT"

echo "============================================"
echo "⚠️  DELETE STACK WARNING"
echo "============================================"
echo "Stack: $STACK_NAME"
echo ""
echo "This will DELETE ALL resources including:"
echo "  - API Gateway"
echo "  - Lambda Functions"
echo "  - DynamoDB Tables (ALL DATA WILL BE LOST)"
echo "  - Cognito User Pool (ALL USERS WILL BE DELETED)"
echo "  - Secrets Manager secrets"
echo ""

if [ "$ENVIRONMENT" == "prod" ]; then
    echo "🚨 PRODUCTION ENVIRONMENT DETECTED 🚨"
    echo ""
    read -p "Type 'DELETE PRODUCTION' to confirm: " confirm
    if [ "$confirm" != "DELETE PRODUCTION" ]; then
        echo "Deletion cancelled."
        exit 0
    fi
else
    read -p "Type 'yes' to confirm deletion: " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Deletion cancelled."
        exit 0
    fi
fi

echo ""
echo "Deleting stack: $STACK_NAME..."

aws cloudformation delete-stack --stack-name "$STACK_NAME"

echo "Waiting for stack deletion to complete..."
aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"

echo ""
echo "Stack $STACK_NAME has been deleted."
