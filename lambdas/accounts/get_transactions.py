"""
GET /accounts/{account_id}/transactions
Fetch transactions for a specific account.
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, not_found, bad_request, internal_error
from shared.auth import require_auth
from shared.database import AccountRepository, TransactionRepository
from shared.validation import (
    get_path_param,
    get_query_param,
    get_query_param_int,
    validate_uuid,
    validate_date
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle get transactions request."""
    try:
        user_id = event["user_id"]
        account_id = get_path_param(event, "account_id")

        if not account_id:
            return bad_request("Account ID is required")

        if not validate_uuid(account_id):
            return bad_request("Invalid account ID format")

        # Verify account belongs to user
        account_repo = AccountRepository()
        account = account_repo.get_account(user_id, account_id)

        if not account:
            return not_found("Account not found")

        # Parse query parameters
        start_date = get_query_param(event, "start_date")
        end_date = get_query_param(event, "end_date")
        limit = get_query_param_int(event, "limit", default=50, min_val=1, max_val=500)
        offset = get_query_param_int(event, "offset", default=0, min_val=0)
        category = get_query_param(event, "category")

        # Validate date formats if provided
        if start_date and not validate_date(start_date):
            return bad_request("Invalid start_date format. Use YYYY-MM-DD")
        if end_date and not validate_date(end_date):
            return bad_request("Invalid end_date format. Use YYYY-MM-DD")

        # Fetch transactions
        txn_repo = TransactionRepository()
        transactions = txn_repo.get_account_transactions(
            user_id,
            account_id,
            limit=limit + 1,  # Fetch one extra to check has_more
            offset=offset
        )

        # Filter by date range if provided
        if start_date:
            transactions = [
                t for t in transactions
                if t.get("date", "")[:10] >= start_date
            ]
        if end_date:
            transactions = [
                t for t in transactions
                if t.get("date", "")[:10] <= end_date
            ]

        # Filter by category if provided
        if category:
            transactions = [
                t for t in transactions
                if t.get("category_name", "").lower() == category.lower()
            ]

        # Check if there are more results
        has_more = len(transactions) > limit
        if has_more:
            transactions = transactions[:limit]

        # Format transactions for response
        formatted_transactions = []
        for txn in transactions:
            formatted_transactions.append({
                "id": txn.get("id"),
                "amount": txn.get("amount", 0),
                "description": txn.get("description"),
                "date": txn.get("date"),
                "category_name": txn.get("category_name"),
                "is_income": txn.get("is_income", False),
                "merchant": txn.get("merchant")
            })

        return success({
            "transactions": formatted_transactions,
            "pagination": {
                "total": len(formatted_transactions) + offset + (1 if has_more else 0),
                "limit": limit,
                "offset": offset,
                "has_more": has_more
            }
        })

    except Exception as e:
        logger.error(f"Error getting transactions: {str(e)}")
        return internal_error("Failed to retrieve transactions")
