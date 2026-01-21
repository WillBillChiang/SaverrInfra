"""
Authentication utilities for Lambda functions.
Handles JWT validation and user context extraction.
"""
import os
import json
import logging
from typing import Any, Dict, Optional, Tuple
from functools import wraps

import boto3
from jose import jwt, JWTError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cognito configuration from environment
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Cognito JWKS URL
COGNITO_ISSUER = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"

# Cache for JWKS keys
_jwks_cache: Optional[Dict] = None


def get_jwks() -> Dict:
    """Fetch and cache JWKS from Cognito."""
    global _jwks_cache
    if _jwks_cache is None:
        import urllib.request
        jwks_url = f"{COGNITO_ISSUER}/.well-known/jwks.json"
        with urllib.request.urlopen(jwks_url) as response:
            _jwks_cache = json.loads(response.read().decode())
    return _jwks_cache


def verify_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Verify a JWT token from Cognito.

    Returns:
        Tuple of (is_valid, claims, error_message)
    """
    try:
        # Get the key id from the token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            return False, None, "Token missing key ID"

        # Find the matching key in JWKS
        jwks = get_jwks()
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break

        if not key:
            return False, None, "Token key not found in JWKS"

        # Verify and decode the token
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID,
            issuer=COGNITO_ISSUER
        )

        # Verify token_use is access or id token
        token_use = claims.get("token_use")
        if token_use not in ["access", "id"]:
            return False, None, f"Invalid token_use: {token_use}"

        return True, claims, None

    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        return False, None, str(e)
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return False, None, "Token verification failed"


def get_user_id_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract user ID from API Gateway event.
    Works with both Lambda authorizer and Cognito authorizer.
    """
    # Try Lambda authorizer context first
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})

    # Lambda authorizer with JWT claims
    if "claims" in authorizer:
        return authorizer["claims"].get("sub")

    # Lambda authorizer with principalId
    if "principalId" in authorizer:
        return authorizer["principalId"]

    # Cognito authorizer
    if "jwt" in authorizer:
        return authorizer["jwt"].get("claims", {}).get("sub")

    return None


def extract_bearer_token(event: Dict[str, Any]) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    headers = event.get("headers", {})
    if not headers:
        return None

    # Headers might be case-insensitive
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header:
        return None

    if not auth_header.startswith("Bearer "):
        return None

    return auth_header[7:]  # Remove "Bearer " prefix


def require_auth(handler):
    """
    Decorator that enforces authentication on a Lambda handler.
    Adds user_id to the event if authentication is successful.
    """
    from shared.response import unauthorized

    @wraps(handler)
    def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        # Check if already authorized by API Gateway authorizer
        user_id = get_user_id_from_event(event)
        if user_id:
            event["user_id"] = user_id
            return handler(event, context)

        # Fall back to manual token verification
        token = extract_bearer_token(event)
        if not token:
            return unauthorized("Missing authentication token")

        is_valid, claims, error_msg = verify_token(token)
        if not is_valid:
            return unauthorized(error_msg or "Invalid token")

        event["user_id"] = claims.get("sub")
        event["claims"] = claims
        return handler(event, context)

    return wrapper
