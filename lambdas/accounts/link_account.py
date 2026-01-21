"""
POST /accounts/link
Initiate account linking process (integrates with Plaid or similar service).
"""
import os
import logging
from typing import Any, Dict

import boto3

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, bad_request, internal_error, service_unavailable
from shared.auth import require_auth
from shared.database import AccountRepository, get_timestamp, generate_id
from shared.validation import parse_body, require_fields, sanitize_string

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Plaid configuration from Secrets Manager
PLAID_SECRET_ARN = os.environ.get("PLAID_SECRET_ARN", "")

secrets_client = boto3.client("secretsmanager")


def get_plaid_credentials() -> Dict[str, str]:
    """Retrieve Plaid API credentials from Secrets Manager."""
    if not PLAID_SECRET_ARN:
        raise ValueError("Plaid secret ARN not configured")

    try:
        response = secrets_client.get_secret_value(SecretId=PLAID_SECRET_ARN)
        import json
        return json.loads(response["SecretString"])
    except Exception as e:
        logger.error(f"Failed to retrieve Plaid credentials: {str(e)}")
        raise


def exchange_public_token(public_token: str, plaid_creds: Dict[str, str]) -> Dict[str, Any]:
    """
    Exchange Plaid public token for access token.
    In production, this would make an actual API call to Plaid.
    """
    import urllib.request
    import json

    plaid_env = plaid_creds.get("environment", "sandbox")
    plaid_host = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com"
    }.get(plaid_env, "https://sandbox.plaid.com")

    payload = json.dumps({
        "client_id": plaid_creds["client_id"],
        "secret": plaid_creds["secret"],
        "public_token": public_token
    }).encode()

    req = urllib.request.Request(
        f"{plaid_host}/item/public_token/exchange",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"Plaid token exchange failed: {str(e)}")
        raise


def get_account_info(access_token: str, plaid_creds: Dict[str, str]) -> Dict[str, Any]:
    """
    Get account information from Plaid using the access token.
    """
    import urllib.request
    import json

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
        f"{plaid_host}/accounts/get",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"Plaid accounts get failed: {str(e)}")
        raise


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle account link request."""
    try:
        user_id = event["user_id"]
        body = parse_body(event)
        require_fields(body, ["public_token"])

        public_token = sanitize_string(body["public_token"])
        institution_id = body.get("institution_id")

        # Get Plaid credentials
        try:
            plaid_creds = get_plaid_credentials()
        except Exception as e:
            logger.error(f"Failed to get Plaid credentials: {str(e)}")
            return service_unavailable("Account linking service temporarily unavailable")

        # Exchange public token for access token
        try:
            exchange_response = exchange_public_token(public_token, plaid_creds)
            access_token = exchange_response.get("access_token")
            item_id = exchange_response.get("item_id")
        except Exception as e:
            logger.error(f"Token exchange failed: {str(e)}")
            return bad_request("Failed to link account. Please try again.")

        # Get account information
        try:
            accounts_response = get_account_info(access_token, plaid_creds)
            plaid_accounts = accounts_response.get("accounts", [])
            institution = accounts_response.get("item", {})
        except Exception as e:
            logger.error(f"Failed to get account info: {str(e)}")
            return bad_request("Failed to retrieve account information")

        if not plaid_accounts:
            return bad_request("No accounts found for this institution")

        # Create account records in database
        repo = AccountRepository()
        created_accounts = []

        for plaid_account in plaid_accounts:
            account_data = {
                "institution_name": institution.get("institution_name", "Unknown"),
                "institution_id": institution_id or institution.get("institution_id"),
                "account_name": plaid_account.get("name", "Account"),
                "account_type": plaid_account.get("type", "checking"),
                "balance": plaid_account.get("balances", {}).get("current", 0),
                "account_number_last4": plaid_account.get("mask", "****"),
                "plaid_account_id": plaid_account.get("account_id"),
                "plaid_item_id": item_id,
                "plaid_access_token": access_token,  # Stored encrypted in DynamoDB
                "is_linked": True,
                "institution_logo": "building.columns"
            }

            created = repo.create_account(user_id, account_data)
            created_accounts.append(created)

        # Return the first account (primary) in response
        primary_account = created_accounts[0] if created_accounts else None

        if not primary_account:
            return internal_error("Failed to create account record")

        return success({
            "account": {
                "id": primary_account.get("id"),
                "institution_name": primary_account.get("institution_name"),
                "account_name": primary_account.get("account_name"),
                "account_type": primary_account.get("account_type"),
                "balance": primary_account.get("balance", 0),
                "last_updated": primary_account.get("last_updated"),
                "is_linked": True,
                "account_number_last4": primary_account.get("account_number_last4")
            },
            "link_status": "success",
            "accounts_linked": len(created_accounts)
        })

    except Exception as e:
        logger.error(f"Account link error: {str(e)}")
        if hasattr(e, "message"):
            return bad_request(e.message)
        return internal_error("Failed to link account")
