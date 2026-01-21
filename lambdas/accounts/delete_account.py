"""
DELETE /accounts/{account_id}
Unlink a bank account.
"""
import os
import logging
from typing import Any, Dict

import boto3

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, not_found, bad_request, internal_error
from shared.auth import require_auth
from shared.database import AccountRepository
from shared.validation import get_path_param, validate_uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Plaid configuration
PLAID_SECRET_ARN = os.environ.get("PLAID_SECRET_ARN", "")

secrets_client = boto3.client("secretsmanager")


def revoke_plaid_access(access_token: str) -> bool:
    """
    Revoke Plaid access token when unlinking an account.
    This is a best practice for security.
    """
    if not PLAID_SECRET_ARN or not access_token:
        return True  # Skip if Plaid not configured or no token

    try:
        import json
        import urllib.request

        # Get Plaid credentials
        response = secrets_client.get_secret_value(SecretId=PLAID_SECRET_ARN)
        plaid_creds = json.loads(response["SecretString"])

        plaid_env = plaid_creds.get("environment", "sandbox")
        plaid_host = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com"
        }.get(plaid_env, "https://sandbox.plaid.com")

        payload = json.dumps({
            "client_id": plaid_creds["client_id"],
            "secret": plaid_creds["secret"],
            "access_token": access_token
        }).encode()

        req = urllib.request.Request(
            f"{plaid_host}/item/remove",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            return True

    except Exception as e:
        logger.warning(f"Failed to revoke Plaid access token: {str(e)}")
        # Continue with account deletion even if Plaid revocation fails
        return False


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle account deletion request."""
    try:
        user_id = event["user_id"]
        account_id = get_path_param(event, "account_id")

        if not account_id:
            return bad_request("Account ID is required")

        if not validate_uuid(account_id):
            return bad_request("Invalid account ID format")

        repo = AccountRepository()

        # Get the account first to verify ownership and get access token
        account = repo.get_account(user_id, account_id)

        if not account:
            return not_found("Account not found")

        # Revoke Plaid access token if present
        plaid_access_token = account.get("plaid_access_token")
        if plaid_access_token:
            revoke_plaid_access(plaid_access_token)

        # Delete the account
        repo.delete_account(user_id, account_id)

        return success({
            "success": True,
            "message": "Account unlinked successfully"
        })

    except Exception as e:
        logger.error(f"Error deleting account: {str(e)}")
        return internal_error("Failed to unlink account")
