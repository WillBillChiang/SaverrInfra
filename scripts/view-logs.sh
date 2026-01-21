#!/bin/bash

# Saverr API - View Logs
# Usage: ./scripts/view-logs.sh [environment] [function-name]

set -e

ENVIRONMENT=${1:-dev}
FUNCTION=${2:-}

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Error: Invalid environment. Use: dev, staging, or prod"
    exit 1
fi

if [ -z "$FUNCTION" ]; then
    echo "Available Lambda functions:"
    echo ""
    echo "Auth:"
    echo "  login, signup, confirm, resend-code, refresh, forgot-password, reset-password"
    echo ""
    echo "Accounts:"
    echo "  accounts-list, accounts-get, accounts-link, accounts-delete, accounts-refresh, accounts-transactions"
    echo ""
    echo "Goals:"
    echo "  goals-list, goals-create, goals-get, goals-update, goals-delete, goals-contribute"
    echo ""
    echo "Plans:"
    echo "  plans-list, plans-create, plans-deactivate"
    echo ""
    echo "Chat:"
    echo "  chat-message, chat-generate-plan, chat-suggest-goals"
    echo ""
    echo "Analytics:"
    echo "  analytics-cashflow, analytics-spending, analytics-budget, analytics-savings"
    echo ""
    echo "Usage: ./scripts/view-logs.sh $ENVIRONMENT [function-name]"
    exit 0
fi

# Map friendly names to actual function names
case $FUNCTION in
    login) FUNC_NAME="saverr-auth-login-$ENVIRONMENT" ;;
    signup) FUNC_NAME="saverr-auth-signup-$ENVIRONMENT" ;;
    confirm) FUNC_NAME="saverr-auth-confirm-$ENVIRONMENT" ;;
    resend-code) FUNC_NAME="saverr-auth-resend-code-$ENVIRONMENT" ;;
    refresh) FUNC_NAME="saverr-auth-refresh-$ENVIRONMENT" ;;
    forgot-password) FUNC_NAME="saverr-auth-forgot-password-$ENVIRONMENT" ;;
    reset-password) FUNC_NAME="saverr-auth-reset-password-$ENVIRONMENT" ;;
    accounts-list) FUNC_NAME="saverr-accounts-list-$ENVIRONMENT" ;;
    accounts-get) FUNC_NAME="saverr-accounts-get-$ENVIRONMENT" ;;
    accounts-link) FUNC_NAME="saverr-accounts-link-$ENVIRONMENT" ;;
    accounts-delete) FUNC_NAME="saverr-accounts-delete-$ENVIRONMENT" ;;
    accounts-refresh) FUNC_NAME="saverr-accounts-refresh-$ENVIRONMENT" ;;
    accounts-transactions) FUNC_NAME="saverr-accounts-transactions-$ENVIRONMENT" ;;
    goals-list) FUNC_NAME="saverr-goals-list-$ENVIRONMENT" ;;
    goals-create) FUNC_NAME="saverr-goals-create-$ENVIRONMENT" ;;
    goals-get) FUNC_NAME="saverr-goals-get-$ENVIRONMENT" ;;
    goals-update) FUNC_NAME="saverr-goals-update-$ENVIRONMENT" ;;
    goals-delete) FUNC_NAME="saverr-goals-delete-$ENVIRONMENT" ;;
    goals-contribute) FUNC_NAME="saverr-goals-contribute-$ENVIRONMENT" ;;
    plans-list) FUNC_NAME="saverr-plans-list-$ENVIRONMENT" ;;
    plans-create) FUNC_NAME="saverr-plans-create-$ENVIRONMENT" ;;
    plans-deactivate) FUNC_NAME="saverr-plans-deactivate-$ENVIRONMENT" ;;
    chat-message) FUNC_NAME="saverr-chat-message-$ENVIRONMENT" ;;
    chat-generate-plan) FUNC_NAME="saverr-chat-generate-plan-$ENVIRONMENT" ;;
    chat-suggest-goals) FUNC_NAME="saverr-chat-suggest-goals-$ENVIRONMENT" ;;
    analytics-cashflow) FUNC_NAME="saverr-analytics-cashflow-$ENVIRONMENT" ;;
    analytics-spending) FUNC_NAME="saverr-analytics-spending-$ENVIRONMENT" ;;
    analytics-budget) FUNC_NAME="saverr-analytics-budget-$ENVIRONMENT" ;;
    analytics-savings) FUNC_NAME="saverr-analytics-savings-$ENVIRONMENT" ;;
    *) FUNC_NAME="$FUNCTION" ;;
esac

LOG_GROUP="/aws/lambda/$FUNC_NAME"

echo "Viewing logs for: $FUNC_NAME"
echo "Log group: $LOG_GROUP"
echo "============================================"
echo ""

# Stream logs
aws logs tail "$LOG_GROUP" --follow --format short
