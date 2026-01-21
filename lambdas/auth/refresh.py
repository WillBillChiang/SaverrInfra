"""
POST /auth/refresh
Refresh an expired access token using a refresh token.
"""
import os
import logging
import hmac
import hashlib
import base64
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, bad_request, unauthorized, internal_error
from shared.validation import parse_body, require_fields

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cognito configuration
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", "")

cognito_client = boto3.client("cognito-idp")


def compute_secret_hash(username: str) -> str:
    """Compute the secret hash for Cognito authentication."""
    if not COGNITO_CLIENT_SECRET:
        return ""

    message = username + COGNITO_CLIENT_ID
    dig = hmac.new(
        COGNITO_CLIENT_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle token refresh request."""
    try:
        body = parse_body(event)
        require_fields(body, ["refresh_token"])

        refresh_token = body["refresh_token"]

        # Build auth parameters
        auth_params = {
            "REFRESH_TOKEN": refresh_token
        }

        # Note: For refresh token flow, we need the username for secret hash
        # but we may not have it. Try without secret hash first if needed.
        try:
            response = cognito_client.initiate_auth(
                ClientId=COGNITO_CLIENT_ID,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters=auth_params
            )
        except cognito_client.exceptions.NotAuthorizedException:
            return unauthorized("Invalid or expired refresh token")
        except cognito_client.exceptions.UserNotFoundException:
            return unauthorized("User not found")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NotAuthorizedException":
                return unauthorized("Invalid or expired refresh token")
            logger.error(f"Cognito refresh error: {str(e)}")
            return internal_error("Token refresh service error")

        auth_result = response.get("AuthenticationResult", {})

        if not auth_result:
            return internal_error("Token refresh failed")

        # Get user info from the new access token
        try:
            user_response = cognito_client.get_user(
                AccessToken=auth_result["AccessToken"]
            )
            user_attributes = {
                attr["Name"]: attr["Value"]
                for attr in user_response.get("UserAttributes", [])
            }
        except ClientError as e:
            logger.error(f"Error fetching user info: {str(e)}")
            user_attributes = {}

        return success({
            "access_token": auth_result["AccessToken"],
            # Refresh token may or may not be returned depending on Cognito settings
            "refresh_token": auth_result.get("RefreshToken", refresh_token),
            "expires_in": auth_result.get("ExpiresIn", 3600),
            "user": {
                "id": user_attributes.get("sub", ""),
                "email": user_attributes.get("email", ""),
                "name": user_attributes.get("name", user_attributes.get("email", ""))
            }
        })

    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        if hasattr(e, "message"):
            return bad_request(e.message)
        return internal_error("An error occurred during token refresh")
