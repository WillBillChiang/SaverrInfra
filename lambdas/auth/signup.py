"""
POST /auth/signup
Register a new user with AWS Cognito.
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

from shared.response import success, created, bad_request, internal_error
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
    """Handle user signup request."""
    try:
        body = parse_body(event)
        require_fields(body, ["email", "password", "name"])
        
        email = sanitize_string(body["email"]).lower()
        password = body["password"]
        name = sanitize_string(body["name"], max_length=100)
        
        # Validate email
        if not validate_email(email):
            return bad_request("Invalid email format", {"field": "email"})
        
        # Validate password length
        if len(password) < 8:
            return bad_request("Password must be at least 8 characters", {"field": "password"})
        
        # Validate name
        if not name:
            return bad_request("Name cannot be empty", {"field": "name"})
        
        # Build user attributes
        user_attributes = [
            {"Name": "email", "Value": email},
            {"Name": "name", "Value": name}
        ]
        
        # Build signup params
        signup_params = {
            "ClientId": COGNITO_CLIENT_ID,
            "Username": email,
            "Password": password,
            "UserAttributes": user_attributes
        }
        
        # Add secret hash if configured
        if COGNITO_CLIENT_SECRET:
            signup_params["SecretHash"] = compute_secret_hash(email)
        
        try:
            response = cognito_client.sign_up(**signup_params)
        except cognito_client.exceptions.UsernameExistsException:
            return bad_request("An account with this email already exists")
        except cognito_client.exceptions.InvalidPasswordException as e:
            return bad_request(f"Invalid password: {str(e)}")
        except cognito_client.exceptions.InvalidParameterException as e:
            return bad_request(f"Invalid parameter: {str(e)}")
        except ClientError as e:
            logger.error(f"Cognito signup error: {str(e)}")
            return internal_error("Registration service error")
        
        user_confirmed = response.get("UserConfirmed", False)
        
        return created({
            "message": "User registered successfully",
            "user_confirmed": user_confirmed,
            "confirmation_required": not user_confirmed,
            "user": {
                "email": email,
                "name": name
            }
        })
    
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return internal_error("Failed to register user")
