"""
POST /accounts/link-token
Create a Plaid Link token for the client to initialize Plaid Link.
This must be called before the user can link their bank account.

Plaid API Reference: https://plaid.com/docs/api/tokens/#linktokencreate
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

from shared.response import success, bad_request, internal_error, service_unavailable
from shared.auth import require_auth
from shared.validation import parse_body

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Plaid configuration
PLAID_SECRET_ARN = os.environ.get("PLAID_SECRET_ARN", "")
PLAID_PRODUCTS = os.environ.get("PLAID_PRODUCTS", "transactions").split(",")
PLAID_COUNTRY_CODES = os.environ.get("PLAID_COUNTRY_CODES", "US").split(",")
PLAID_REDIRECT_URI = os.environ.get("PLAID_REDIRECT_URI", "")

secrets_client = boto3.client("secretsmanager")


def get_plaid_credentials() -> Dict[str, str]:
    """Retrieve Plaid API credentials from Secrets Manager."""
    if not PLAID_SECRET_ARN:
        raise ValueError("Plaid secret ARN not configured")

    response = secrets_client.get_secret_value(SecretId=PLAID_SECRET_ARN)
    return json.loads(response["SecretString"])


def get_plaid_host(environment: str) -> str:
    """Get the Plaid API host for the given environment."""
    hosts = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com"
    }
    return hosts.get(environment, "https://sandbox.plaid.com")


def create_link_token_request(
    user_id: str,
    plaid_creds: Dict[str, str],
    access_token: str = None
) -> Dict[str, Any]:
    """
    Create a Plaid Link token.
    
    Args:
        user_id: The unique user identifier
        plaid_creds: Plaid API credentials
        access_token: Optional - for update mode (re-linking expired accounts)
    
    Returns:
        Plaid Link token response
    """
    plaid_host = get_plaid_host(plaid_creds.get("environment", "sandbox"))

    # Build the request payload
    payload = {
        "client_id": plaid_creds["client_id"],
        "secret": plaid_creds["secret"],
        "client_name": "Saverr",
        "user": {
            "client_user_id": user_id
        },
        "products": PLAID_PRODUCTS,
        "country_codes": PLAID_COUNTRY_CODES,
        "language": "en"
    }

    # If redirect URI is configured (for OAuth institutions)
    if PLAID_REDIRECT_URI:
        payload["redirect_uri"] = PLAID_REDIRECT_URI

    # If access_token is provided, this is an update mode request
    if access_token:
        payload["access_token"] = access_token
        # Remove products for update mode
        del payload["products"]

    req = urllib.request.Request(
        f"{plaid_host}/link/token/create",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        logger.error(f"Plaid API error: {e.code} - {error_body}")
        raise Exception(f"Plaid API error: {error_body}")


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle create link token request.
    
    Request body (optional):
    {
        "access_token": "access-sandbox-xxx"  // For update mode only
    }
    
    Response:
    {
        "link_token": "link-sandbox-xxx",
        "expiration": "2024-01-21T12:00:00Z",
        "request_id": "xxx"
    }
    """
    try:
        user_id = event["user_id"]

        # Parse optional body for update mode
        body = parse_body(event) or {}
        access_token = body.get("access_token")

        # Get Plaid credentials
        try:
            plaid_creds = get_plaid_credentials()
        except Exception as e:
            logger.error(f"Failed to get Plaid credentials: {str(e)}")
            return service_unavailable("Account linking service temporarily unavailable")

        # Create link token
        try:
            response = create_link_token_request(user_id, plaid_creds, access_token)
        except Exception as e:
            logger.error(f"Failed to create link token: {str(e)}")
            return internal_error("Failed to create link token")

        return success({
            "link_token": response.get("link_token"),
            "expiration": response.get("expiration"),
            "request_id": response.get("request_id")
        })

    except Exception as e:
        logger.error(f"Create link token error: {str(e)}")
        return internal_error("Failed to create link token")
