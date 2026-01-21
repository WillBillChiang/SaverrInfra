"""
PUT /goals/{goal_id}
Update an existing goal.
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, not_found, bad_request, internal_error
from shared.auth import require_auth
from shared.database import GoalRepository
from shared.validation import (
    parse_body,
    get_path_param,
    validate_uuid,
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
    """Handle update goal request."""
    try:
        user_id = event["user_id"]
        goal_id = get_path_param(event, "goal_id")
        
        if not goal_id:
            return bad_request("Goal ID is required")
        
        if not validate_uuid(goal_id):
            return bad_request("Invalid goal ID format")
        
        body = parse_body(event)
        
        if not body:
            return bad_request("Request body cannot be empty")
        
        repo = GoalRepository()
        
        # Verify goal exists
        existing_goal = repo.get_goal(user_id, goal_id)
        if not existing_goal:
            return not_found("Goal not found")
        
        # Build update dict
        updates = {}
        
        if "title" in body:
            title = sanitize_string(body["title"], max_length=200)
            if not title:
                return bad_request("Title cannot be empty")
            updates["title"] = title
        
        if "description" in body:
            updates["description"] = sanitize_string(body["description"], max_length=1000)
        
        if "target_amount" in body:
            is_valid, error = validate_amount(body["target_amount"])
            if not is_valid:
                return bad_request(f"Invalid target_amount: {error}")
            if body["target_amount"] <= 0:
                return bad_request("Target amount must be greater than 0")
            updates["target_amount"] = body["target_amount"]
        
        if "current_amount" in body:
            is_valid, error = validate_amount(body["current_amount"])
            if not is_valid:
                return bad_request(f"Invalid current_amount: {error}")
            updates["current_amount"] = body["current_amount"]
        
        if "target_date" in body:
            if body["target_date"] and not validate_date(body["target_date"]):
                return bad_request("Invalid target_date format. Use YYYY-MM-DD")
            updates["target_date"] = body["target_date"]
        
        if "category" in body:
            if body["category"] not in VALID_CATEGORIES:
                return bad_request(f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}")
            updates["category"] = body["category"]
        
        if "priority" in body:
            if not isinstance(body["priority"], int) or body["priority"] < 0:
                return bad_request("Priority must be a non-negative integer")
            updates["priority"] = body["priority"]
        
        if not updates:
            return bad_request("No valid fields to update")
        
        # Update goal
        updated_goal = repo.update_goal(user_id, goal_id, updates)
        
        return success({
            "goal": {
                "id": updated_goal.get("id"),
                "title": updated_goal.get("title"),
                "description": updated_goal.get("description"),
                "target_amount": updated_goal.get("target_amount", 0),
                "current_amount": updated_goal.get("current_amount", 0),
                "target_date": updated_goal.get("target_date"),
                "created_at": updated_goal.get("created_at"),
                "category": updated_goal.get("category"),
                "is_ai_generated": updated_goal.get("is_ai_generated", False),
                "priority": updated_goal.get("priority", 0),
                "progress": updated_goal.get("progress", 0)
            }
        })
    
    except ValidationError as e:
        return bad_request(e.message)
    except Exception as e:
        logger.error(f"Error updating goal: {str(e)}")
        return internal_error("Failed to update goal")
