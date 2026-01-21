"""
GET /accounts/{account_id}
Fetch details for a specific account.
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, not_found, bad_request, internal_error
from shared.auth import require_auth
from shared.database import AccountRepository
from shared.validation import get_path_param, validate_uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle get account request."""
    try:
        user_id = event["user_id"]
        account_id = get_path_param(event, "account_id")

        if not account_id:
            return bad_request("Account ID is required")

        if not validate_uuid(account_id):
            return bad_request("Invalid account ID format")

        repo = AccountRepository()
        account = repo.get_account(user_id, account_id)

        if not account:
            return not_found("Account not found")

        return success({
            "id": account.get("id"),
            "institution_name": account.get("institution_name"),
            "account_name": account.get("account_name"),
            "account_type": account.get("account_type"),
            "balance": account.get("balance", 0),
            "last_updated": account.get("last_updated"),
            "is_linked": account.get("is_linked", True),
            "account_number_last4": account.get("account_number_last4"),
            "institution_logo": account.get("institution_logo", "building.columns"),
            "routing_number_last4": account.get("routing_number_last4")
        })

    except Exception as e:
        logger.error(f"Error getting account: {str(e)}")
        return internal_error("Failed to retrieve account")
