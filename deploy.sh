#!/bin/bash

# Saverr API Deployment Script
# Usage: ./deploy.sh [environment] [options]
# 
# Environments: dev, staging, prod
# Options:
#   --build-only    Only build, don't deploy
#   --skip-build    Skip build step
#   --guided        Run guided deployment
#   --sync          Enable SAM sync (hot reload for dev)

set -e

ENVIRONMENT=${1:-dev}
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BUILD_ONLY=false
SKIP_BUILD=false
GUIDED=false
SYNC=false

# Parse additional arguments
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --guided)
            GUIDED=true
            shift
            ;;
        --sync)
            SYNC=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================"
echo "Saverr API Deployment"
echo "============================================"
echo "Environment: $ENVIRONMENT"
echo "Build Only:  $BUILD_ONLY"
echo "Skip Build:  $SKIP_BUILD"
echo "Guided:      $GUIDED"
echo "Sync Mode:   $SYNC"
echo "============================================"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Error: Invalid environment. Use: dev, staging, or prod"
    echo ""
    echo "Usage: ./deploy.sh [environment] [options]"
    echo ""
    echo "Environments:"
    echo "  dev      Development environment (sandbox Plaid)"
    echo "  staging  Staging environment (development Plaid)"
    echo "  prod     Production environment (production Plaid)"
    echo ""
    echo "Options:"
    echo "  --build-only    Only build, don't deploy"
    echo "  --skip-build    Skip build step"
    echo "  --guided        Run guided deployment"
    echo "  --sync          Enable SAM sync (hot reload for dev)"
    exit 1
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "Error: SAM CLI is not installed"
    echo "Install it with: brew install aws-sam-cli"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS CLI is not configured or credentials are invalid"
    exit 1
fi

cd "$SCRIPT_DIR"

# Build the application
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo "Building SAM application..."
    sam build --config-env "$ENVIRONMENT"
fi

if [ "$BUILD_ONLY" = true ]; then
    echo ""
    echo "Build complete. Skipping deployment."
    exit 0
fi

# Deploy or sync based on options
echo ""
if [ "$SYNC" = true ]; then
    echo "Starting SAM sync for $ENVIRONMENT (hot reload enabled)..."
    sam sync --config-env "$ENVIRONMENT" --watch
elif [ "$GUIDED" = true ]; then
    echo "Running guided deployment..."
    sam deploy --guided
else
    echo "Deploying to $ENVIRONMENT..."
    
    if [ "$ENVIRONMENT" == "prod" ]; then
        # Production requires confirmation
        echo ""
        echo "⚠️  PRODUCTION DEPLOYMENT"
        echo "You are about to deploy to PRODUCTION."
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            echo "Deployment cancelled."
            exit 0
        fi
        sam deploy --config-env prod
    else
        # Dev and staging can be deployed without confirmation
        sam deploy --config-env "$ENVIRONMENT" --no-confirm-changeset
    fi
fi

# Get outputs
echo ""
echo "============================================"
echo "Deployment Complete!"
echo "============================================"

STACK_NAME="saverr-api-$ENVIRONMENT"
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text 2>/dev/null || echo "Stack not found")

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text 2>/dev/null || echo "")

USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text 2>/dev/null || echo "")

echo ""
echo "Environment:           $ENVIRONMENT"
echo "Stack Name:            $STACK_NAME"
echo "API Endpoint:          $API_ENDPOINT"
echo "Cognito User Pool ID:  $USER_POOL_ID"
echo "Cognito Client ID:     $USER_POOL_CLIENT_ID"
echo ""

# Save outputs to environment file
OUTPUT_FILE="$SCRIPT_DIR/environments/${ENVIRONMENT}-outputs.json"
cat > "$OUTPUT_FILE" << EOF
{
  "Environment": "$ENVIRONMENT",
  "StackName": "$STACK_NAME",
  "ApiEndpoint": "$API_ENDPOINT",
  "CognitoUserPoolId": "$USER_POOL_ID",
  "CognitoClientId": "$USER_POOL_CLIENT_ID",
  "Region": "us-east-1",
  "DeployedAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
echo "Outputs saved to: $OUTPUT_FILE"
echo ""
echo "Next steps:"
echo "1. Update Plaid credentials in AWS Secrets Manager:"
echo "   aws secretsmanager update-secret --secret-id saverr/plaid/$ENVIRONMENT --secret-string '{...}'"
echo "2. Configure your iOS app with the above settings"
echo ""
