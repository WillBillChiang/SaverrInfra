"""
POST /auth/reset-password
Complete password reset with verification code.
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
    """Handle password reset request."""
    try:
        body = parse_body(event)
        require_fields(body, ["email", "code", "new_password"])
        
        email = sanitize_string(body["email"]).lower()
        code = sanitize_string(body["code"])
        new_password = body["new_password"]
        
        if not validate_email(email):
            return bad_request("Invalid email format")
        
        if not code or len(code) < 4:
            return bad_request("Invalid reset code")
        
        if len(new_password) < 8:
            return bad_request("Password must be at least 8 characters")
        
        # Build confirm forgot password params
        confirm_params = {
            "ClientId": COGNITO_CLIENT_ID,
            "Username": email,
            "ConfirmationCode": code,
            "Password": new_password
        }
        
        if COGNITO_CLIENT_SECRET:
            confirm_params["SecretHash"] = compute_secret_hash(email)
        
        try:
            cognito_client.confirm_forgot_password(**confirm_params)
        except cognito_client.exceptions.CodeMismatchException:
            return bad_request("Invalid reset code")
        except cognito_client.exceptions.ExpiredCodeException:
            return bad_request("Reset code has expired. Please request a new one.")
        except cognito_client.exceptions.UserNotFoundException:
            return bad_request("User not found")
        except cognito_client.exceptions.InvalidPasswordException as e:
            return bad_request(f"Invalid password: {str(e)}")
        except ClientError as e:
            logger.error(f"Cognito reset password error: {str(e)}")
            return internal_error("Service error")
        
        return success({
            "message": "Password reset successfully"
        })
    
    except Exception as e:
        logger.error(f"Reset password error: {str(e)}")
        return internal_error("Failed to reset password")
