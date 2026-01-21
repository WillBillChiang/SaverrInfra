"""
POST /accounts/{account_id}/refresh
Refresh account balance and transactions from Plaid.
"""
import os
import logging
import json
import urllib.request
from typing import Any, Dict

import boto3

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, not_found, bad_request, internal_error, service_unavailable
from shared.auth import require_auth
from shared.database import AccountRepository, get_timestamp
from shared.validation import get_path_param, validate_uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Plaid configuration
PLAID_SECRET_ARN = os.environ.get("PLAID_SECRET_ARN", "")

secrets_client = boto3.client("secretsmanager")


def get_plaid_credentials() -> Dict[str, str]:
    """Retrieve Plaid API credentials from Secrets Manager."""
    if not PLAID_SECRET_ARN:
        raise ValueError("Plaid secret ARN not configured")

    response = secrets_client.get_secret_value(SecretId=PLAID_SECRET_ARN)
    return json.loads(response["SecretString"])


def refresh_account_balance(access_token: str, plaid_creds: Dict[str, str]) -> Dict[str, Any]:
    """Fetch latest account balance from Plaid."""
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
        f"{plaid_host}/accounts/balance/get",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle account refresh request."""
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

        # Check if account has Plaid access token
        plaid_access_token = account.get("plaid_access_token")

        if plaid_access_token:
            # Refresh from Plaid
            try:
                plaid_creds = get_plaid_credentials()
                balance_response = refresh_account_balance(plaid_access_token, plaid_creds)

                # Find the matching account in the response
                plaid_account_id = account.get("plaid_account_id")
                new_balance = account.get("balance", 0)

                for plaid_account in balance_response.get("accounts", []):
                    if plaid_account.get("account_id") == plaid_account_id:
                        new_balance = plaid_account.get("balances", {}).get("current", 0)
                        break

                # Update account in database
                updated_time = get_timestamp()
                repo.update(
                    f"USER#{user_id}",
                    f"ACCOUNT#{account_id}",
                    {
                        "balance": new_balance,
                        "last_updated": updated_time
                    }
                )

                return success({
                    "balance": new_balance,
                    "last_updated": updated_time
                })

            except Exception as e:
                logger.error(f"Plaid refresh failed: {str(e)}")
                return service_unavailable("Unable to refresh account data. Please try again later.")

        else:
            # No Plaid token - just update the timestamp
            updated_time = get_timestamp()
            repo.update(
                f"USER#{user_id}",
                f"ACCOUNT#{account_id}",
                {"last_updated": updated_time}
            )

            return success({
                "balance": account.get("balance", 0),
                "last_updated": updated_time
            })

    except Exception as e:
        logger.error(f"Error refreshing account: {str(e)}")
        return internal_error("Failed to refresh account")
