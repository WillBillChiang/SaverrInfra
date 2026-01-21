"""
POST /goals/{goal_id}/contribute
Add a contribution to a goal.
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, not_found, bad_request, internal_error
from shared.auth import require_auth
from shared.database import GoalRepository, generate_id, get_timestamp
from shared.validation import (
    parse_body,
    get_path_param,
    require_fields,
    validate_uuid,
    validate_amount,
    sanitize_string,
    ValidationError
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle goal contribution request."""
    try:
        user_id = event["user_id"]
        goal_id = get_path_param(event, "goal_id")
        
        if not goal_id:
            return bad_request("Goal ID is required")
        
        if not validate_uuid(goal_id):
            return bad_request("Invalid goal ID format")
        
        body = parse_body(event)
        require_fields(body, ["amount"])
        
        amount = body["amount"]
        note = sanitize_string(body.get("note", ""), max_length=500)
        
        # Validate amount
        is_valid, error = validate_amount(amount)
        if not is_valid:
            return bad_request(f"Invalid amount: {error}")
        
        if amount <= 0:
            return bad_request("Contribution amount must be greater than 0")
        
        repo = GoalRepository()
        
        # Get existing goal
        goal = repo.get_goal(user_id, goal_id)
        if not goal:
            return not_found("Goal not found")
        
        # Calculate new current amount
        new_current_amount = goal.get("current_amount", 0) + amount
        
        # Update goal with new amount
        updated_goal = repo.update_goal(user_id, goal_id, {
            "current_amount": new_current_amount
        })
        
        # Create contribution record
        contribution = {
            "id": generate_id(),
            "amount": amount,
            "date": get_timestamp(),
            "note": note
        }
        
        return success({
            "goal": {
                "id": updated_goal.get("id"),
                "current_amount": updated_goal.get("current_amount", 0),
                "progress": updated_goal.get("progress", 0)
            },
            "contribution": contribution
        })
    
    except ValidationError as e:
        return bad_request(e.message)
    except Exception as e:
        logger.error(f"Error contributing to goal: {str(e)}")
        return internal_error("Failed to add contribution")
