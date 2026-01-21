"""
POST /goals
Create a new financial goal.
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, created, bad_request, internal_error
from shared.auth import require_auth
from shared.database import GoalRepository
from shared.validation import (
    parse_body,
    require_fields,
    sanitize_string,
    validate_date,
    validate_amount,
    ValidationError
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Valid goal categories
VALID_CATEGORIES = [
    "savings", "debt_payoff", "emergency", "investment",
    "purchase", "retirement", "vacation", "custom"
]


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle create goal request."""
    try:
        user_id = event["user_id"]
        body = parse_body(event)
        
        # Validate required fields
        require_fields(body, ["title", "target_amount"])
        
        title = sanitize_string(body["title"], max_length=200)
        description = sanitize_string(body.get("description", ""), max_length=1000)
        target_amount = body["target_amount"]
        current_amount = body.get("current_amount", 0)
        target_date = body.get("target_date")
        category = body.get("category", "custom")
        
        # Validate title
        if not title:
            return bad_request("Title cannot be empty")
        
        # Validate amounts
        is_valid, error = validate_amount(target_amount)
        if not is_valid:
            return bad_request(f"Invalid target_amount: {error}")
        
        is_valid, error = validate_amount(current_amount)
        if not is_valid:
            return bad_request(f"Invalid current_amount: {error}")
        
        if target_amount <= 0:
            return bad_request("Target amount must be greater than 0")
        
        # Validate target date if provided
        if target_date and not validate_date(target_date):
            return bad_request("Invalid target_date format. Use YYYY-MM-DD")
        
        # Validate category
        if category not in VALID_CATEGORIES:
            return bad_request(f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}")
        
        # Calculate progress
        progress = current_amount / target_amount if target_amount > 0 else 0
        
        # Create goal
        repo = GoalRepository()
        goal = repo.create_goal(user_id, {
            "title": title,
            "description": description,
            "target_amount": target_amount,
            "current_amount": current_amount,
            "target_date": target_date,
            "category": category,
            "is_ai_generated": False,
            "priority": 0,
            "progress": progress
        })
        
        return created({
            "goal": {
                "id": goal.get("id"),
                "title": goal.get("title"),
                "description": goal.get("description"),
                "target_amount": goal.get("target_amount"),
                "current_amount": goal.get("current_amount"),
                "target_date": goal.get("target_date"),
                "created_at": goal.get("created_at"),
                "category": goal.get("category"),
                "is_ai_generated": goal.get("is_ai_generated", False),
                "priority": goal.get("priority", 0),
                "progress": goal.get("progress", 0)
            }
        })
    
    except ValidationError as e:
        return bad_request(e.message)
    except Exception as e:
        logger.error(f"Error creating goal: {str(e)}")
        return internal_error("Failed to create goal")
