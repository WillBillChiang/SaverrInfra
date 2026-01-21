"""
POST /auth/resend-code
Resend verification code for email confirmation.
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

from shared.response import success, bad_request, internal_error
from shared.validation import parse_body, require_fields, validate_email, sanitize_string

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cognito configuration
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
    """Handle resend confirmation code request."""
    try:
        body = parse_body(event)
        require_fields(body, ["email"])
        
        email = sanitize_string(body["email"]).lower()
        
        if not validate_email(email):
            return bad_request("Invalid email format")
        
        # Build resend params
        resend_params = {
            "ClientId": COGNITO_CLIENT_ID,
            "Username": email
        }
        
        if COGNITO_CLIENT_SECRET:
            resend_params["SecretHash"] = compute_secret_hash(email)
        
        try:
            cognito_client.resend_confirmation_code(**resend_params)
        except cognito_client.exceptions.UserNotFoundException:
            # Don't reveal if user exists or not
            return success({"message": "If an account exists with this email, a new code has been sent."})
        except cognito_client.exceptions.InvalidParameterException:
            return bad_request("User is already confirmed")
        except cognito_client.exceptions.LimitExceededException:
            return bad_request("Too many requests. Please try again later.")
        except ClientError as e:
            logger.error(f"Cognito resend error: {str(e)}")
            return internal_error("Service error")
        
        return success({
            "message": "Confirmation code sent successfully"
        })
    
    except Exception as e:
        logger.error(f"Resend code error: {str(e)}")
        return internal_error("Failed to resend code")
