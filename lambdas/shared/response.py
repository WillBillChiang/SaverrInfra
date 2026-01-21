"""
Shared response utilities for Lambda functions.
Provides consistent response formatting across all API endpoints.
"""
import json
from typing import Any, Dict, Optional


def create_response(
    status_code: int,
    body: Any,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Create a standardized API Gateway response."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
    }

    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body) if body is not None else ""
    }


def success(body: Any, status_code: int = 200) -> Dict[str, Any]:
    """Return a successful response."""
    return create_response(status_code, body)


def created(body: Any) -> Dict[str, Any]:
    """Return a 201 Created response."""
    return create_response(201, body)


def no_content() -> Dict[str, Any]:
    """Return a 204 No Content response."""
    return create_response(204, None)


def error(
    code: str,
    message: str,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Return an error response in standard format."""
    error_body = {
        "error": {
            "code": code,
            "message": message
        }
    }
    if details:
        error_body["error"]["details"] = details

    return create_response(status_code, error_body)


def bad_request(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a 400 Bad Request response."""
    return error("VALIDATION_ERROR", message, 400, details)


def unauthorized(message: str = "Invalid or expired authentication token") -> Dict[str, Any]:
    """Return a 401 Unauthorized response."""
    return error("UNAUTHORIZED", message, 401)


def forbidden(message: str = "You don't have permission to access this resource") -> Dict[str, Any]:
    """Return a 403 Forbidden response."""
    return error("FORBIDDEN", message, 403)


def not_found(message: str = "Resource not found") -> Dict[str, Any]:
    """Return a 404 Not Found response."""
    return error("NOT_FOUND", message, 404)


def rate_limited(message: str = "Too many requests") -> Dict[str, Any]:
    """Return a 429 Too Many Requests response."""
    return error("RATE_LIMITED", message, 429)


def internal_error(message: str = "An internal error occurred") -> Dict[str, Any]:
    """Return a 500 Internal Server Error response."""
    return error("INTERNAL_ERROR", message, 500)


def service_unavailable(message: str = "Service temporarily unavailable") -> Dict[str, Any]:
    """Return a 503 Service Unavailable response."""
    return error("SERVICE_UNAVAILABLE", message, 503)
