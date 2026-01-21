"""
GET /goals
Fetch all financial goals for the authenticated user.
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, internal_error
from shared.auth import require_auth
from shared.database import GoalRepository
from shared.validation import get_query_param, validate_enum, ValidationError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle list goals request."""
    try:
        user_id = event["user_id"]
        
        # Parse query parameters
        status = get_query_param(event, "status", default="active")
        category = get_query_param(event, "category")
        
        # Validate status
        try:
            validate_enum(status, ["active", "completed", "all"], "status")
        except ValidationError as e:
            from shared.response import bad_request
            return bad_request(e.message)
        
        repo = GoalRepository()
        goals = repo.get_user_goals(user_id, status=status)
        
        # Filter by category if provided
        if category:
            goals = [g for g in goals if g.get("category", "").lower() == category.lower()]
        
        # Format response
        formatted_goals = []
        for goal in goals:
            formatted_goals.append({
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
            })
        
        return success({"goals": formatted_goals})
    
    except Exception as e:
        logger.error(f"Error listing goals: {str(e)}")
        return internal_error("Failed to retrieve goals")
