"""
Input validation utilities for Lambda functions.
Provides request body parsing and validation helpers.
"""
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(message)


def parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON body from API Gateway event."""
    body = event.get("body")
    if not body:
        return {}

    if isinstance(body, dict):
        return body

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON in request body")


def get_path_param(event: Dict[str, Any], param_name: str) -> Optional[str]:
    """Get a path parameter from the event."""
    path_params = event.get("pathParameters") or {}
    return path_params.get(param_name)


def get_query_param(
    event: Dict[str, Any],
    param_name: str,
    default: Optional[str] = None
) -> Optional[str]:
    """Get a query parameter from the event."""
    query_params = event.get("queryStringParameters") or {}
    return query_params.get(param_name, default)


def get_query_param_int(
    event: Dict[str, Any],
    param_name: str,
    default: int = 0,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> int:
    """Get an integer query parameter with optional bounds."""
    value = get_query_param(event, param_name)
    if value is None:
        return default

    try:
        int_value = int(value)
    except ValueError:
        raise ValidationError(f"Invalid integer value for {param_name}", param_name)

    if min_val is not None and int_value < min_val:
        int_value = min_val
    if max_val is not None and int_value > max_val:
        int_value = max_val

    return int_value


def get_query_param_bool(
    event: Dict[str, Any],
    param_name: str,
    default: bool = False
) -> bool:
    """Get a boolean query parameter."""
    value = get_query_param(event, param_name)
    if value is None:
        return default

    return value.lower() in ("true", "1", "yes")


def require_fields(data: Dict[str, Any], fields: List[str]) -> None:
    """Validate that required fields are present."""
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing)}",
            missing[0]
        )


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_uuid(value: str) -> bool:
    """Validate UUID format."""
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    return bool(re.match(pattern, value.lower()))


def validate_date(value: str) -> bool:
    """Validate ISO 8601 date format (YYYY-MM-DD)."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_datetime(value: str) -> bool:
    """Validate ISO 8601 datetime format."""
    try:
        # Handle various ISO 8601 formats
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_month(value: str) -> bool:
    """Validate YYYY-MM format."""
    pattern = r"^\d{4}-(0[1-9]|1[0-2])$"
    return bool(re.match(pattern, value))


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize a string input."""
    if not isinstance(value, str):
        return str(value)

    # Trim whitespace
    value = value.strip()

    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length]

    return value


def validate_amount(value: Union[int, float]) -> Tuple[bool, Optional[str]]:
    """Validate a monetary amount."""
    if not isinstance(value, (int, float)):
        return False, "Amount must be a number"

    if value < 0:
        return False, "Amount cannot be negative"

    # Check for reasonable precision (2 decimal places max for currency)
    if isinstance(value, float):
        str_value = f"{value:.10f}"
        decimal_part = str_value.split(".")[1]
        significant_decimals = len(decimal_part.rstrip("0"))
        if significant_decimals > 2:
            return False, "Amount cannot have more than 2 decimal places"

    return True, None


def validate_enum(value: str, allowed_values: List[str], field_name: str) -> None:
    """Validate that a value is in the allowed list."""
    if value not in allowed_values:
        raise ValidationError(
            f"Invalid value for {field_name}. Must be one of: {', '.join(allowed_values)}",
            field_name
        )
