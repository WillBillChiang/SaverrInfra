"""
GET /accounts
Fetch all linked bank accounts for the authenticated user.
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, internal_error
from shared.auth import require_auth
from shared.database import AccountRepository

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle list accounts request."""
    try:
        user_id = event["user_id"]
        repo = AccountRepository()

        accounts = repo.get_user_accounts(user_id)

        # Calculate total balance
        total_balance = sum(
            acc.get("balance", 0)
            for acc in accounts
            if acc.get("is_linked", True)
        )

        # Format response
        formatted_accounts = []
        for acc in accounts:
            formatted_accounts.append({
                "id": acc.get("id"),
                "institution_name": acc.get("institution_name"),
                "account_name": acc.get("account_name"),
                "account_type": acc.get("account_type"),
                "balance": acc.get("balance", 0),
                "last_updated": acc.get("last_updated"),
                "is_linked": acc.get("is_linked", True),
                "account_number_last4": acc.get("account_number_last4"),
                "institution_logo": acc.get("institution_logo", "building.columns")
            })

        return success({
            "accounts": formatted_accounts,
            "total_balance": total_balance
        })

    except Exception as e:
        logger.error(f"Error listing accounts: {str(e)}")
        return internal_error("Failed to retrieve accounts")
