"""
POST /auth/login
Authenticate a user using AWS Cognito and return tokens.
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
from shared.validation import parse_body, require_fields, validate_email, sanitize_string

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
    """Handle user login request."""
    try:
        body = parse_body(event)
        require_fields(body, ["email", "password"])

        email = sanitize_string(body["email"]).lower()
        password = body["password"]

        if not validate_email(email):
            return bad_request("Invalid email format", {"field": "email"})

        # Build auth parameters
        auth_params = {
            "USERNAME": email,
            "PASSWORD": password
        }

        # Add secret hash if client secret is configured
        if COGNITO_CLIENT_SECRET:
            auth_params["SECRET_HASH"] = compute_secret_hash(email)

        # Authenticate with Cognito
        try:
            response = cognito_client.initiate_auth(
                ClientId=COGNITO_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters=auth_params
            )
        except cognito_client.exceptions.NotAuthorizedException:
            return unauthorized("Invalid email or password")
        except cognito_client.exceptions.UserNotFoundException:
            # Return same message as invalid password to prevent user enumeration
            return unauthorized("Invalid email or password")
        except cognito_client.exceptions.UserNotConfirmedException:
            return bad_request("Please verify your email address before logging in")
        except ClientError as e:
            logger.error(f"Cognito authentication error: {str(e)}")
            return internal_error("Authentication service error")

        # Extract authentication result
        auth_result = response.get("AuthenticationResult", {})

        if not auth_result:
            # Handle challenge responses (MFA, etc.)
            challenge = response.get("ChallengeName")
            if challenge:
                return bad_request(f"Additional authentication required: {challenge}")
            return internal_error("Authentication failed")

        # Get user info from Cognito
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
            "refresh_token": auth_result.get("RefreshToken"),
            "expires_in": auth_result.get("ExpiresIn", 3600),
            "user": {
                "id": user_attributes.get("sub", ""),
                "email": email,
                "name": user_attributes.get("name", user_attributes.get("email", email))
            }
        })

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        if hasattr(e, "message"):
            return bad_request(e.message)
        return internal_error("An error occurred during login")
