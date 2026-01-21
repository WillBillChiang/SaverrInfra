"""
GET /goals/{goal_id}
Fetch details for a specific goal.
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
    """Handle get goal request."""
    try:
        user_id = event["user_id"]
        goal_id = get_path_param(event, "goal_id")
        
        if not goal_id:
            return bad_request("Goal ID is required")
        
        if not validate_uuid(goal_id):
            return bad_request("Invalid goal ID format")
        
        repo = GoalRepository()
        goal = repo.get_goal(user_id, goal_id)
        
        if not goal:
            return not_found("Goal not found")
        
        return success({
            "goal": {
                "id": goal.get("id"),
                "title": goal.get("title"),
                "description": goal.get("description"),
                "target_amount": goal.get("target_amount", 0),
                "current_amount": goal.get("current_amount", 0),
                "target_date": goal.get("target_date"),
                "created_at": goal.get("created_at"),
                "category": goal.get("category"),
                "is_ai_generated": goal.get("is_ai_generated", False),
                "priority": goal.get("priority", 0),
                "progress": goal.get("progress", 0)
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting goal: {str(e)}")
        return internal_error("Failed to retrieve goal")
