"""
DELETE /goals/{goal_id}
Delete a financial goal.
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
from shared.validation import get_path_param, validate_uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle delete goal request."""
    try:
        user_id = event["user_id"]
        goal_id = get_path_param(event, "goal_id")
        
        if not goal_id:
            return bad_request("Goal ID is required")
        
        if not validate_uuid(goal_id):
            return bad_request("Invalid goal ID format")
        
        repo = GoalRepository()
        
        # Verify goal exists
        existing_goal = repo.get_goal(user_id, goal_id)
        if not existing_goal:
            return not_found("Goal not found")
        
        # Delete the goal
        repo.delete_goal(user_id, goal_id)
        
        return success({
            "success": True,
            "message": "Goal deleted successfully"
        })
    
    except Exception as e:
        logger.error(f"Error deleting goal: {str(e)}")
        return internal_error("Failed to delete goal")
