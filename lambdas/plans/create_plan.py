"""
POST /plans
Create a new financial plan (typically from AI chat).
"""
import os
import logging
from typing import Any, Dict, List

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, created, bad_request, internal_error
from shared.auth import require_auth
from shared.database import PlanRepository
from shared.validation import (
    parse_body,
    require_fields,
    sanitize_string,
    validate_amount,
    ValidationError
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle create plan request."""
    try:
        user_id = event["user_id"]
        body = parse_body(event)
        
        # Validate required fields
        require_fields(body, ["summary"])
        
        summary = sanitize_string(body["summary"], max_length=2000)
        recommendations = body.get("recommendations", [])
        monthly_target_savings = body.get("monthly_target_savings", 0)
        goal_ids = body.get("goal_ids", [])
        
        # Validate summary
        if not summary:
            return bad_request("Summary cannot be empty")
        
        # Validate recommendations is a list
        if not isinstance(recommendations, list):
            return bad_request("Recommendations must be a list")
        
        # Sanitize recommendations
        recommendations = [
            sanitize_string(r, max_length=500) 
            for r in recommendations 
            if isinstance(r, str)
        ]
        
        # Validate monthly target savings
        if monthly_target_savings:
            is_valid, error = validate_amount(monthly_target_savings)
            if not is_valid:
                return bad_request(f"Invalid monthly_target_savings: {error}")
        
        # Validate goal_ids is a list
        if not isinstance(goal_ids, list):
            return bad_request("goal_ids must be a list")
        
        # Create plan
        repo = PlanRepository()
        
        # Deactivate existing active plans
        existing_plans = repo.get_user_plans(user_id, active_only=True)
        for existing in existing_plans:
            repo.deactivate_plan(user_id, existing.get("id"))
        
        plan = repo.create_plan(user_id, {
            "summary": summary,
            "recommendations": recommendations,
            "monthly_target_savings": monthly_target_savings,
            "goal_ids": goal_ids,
            "is_active": True
        })
        
        return created({
            "plan": {
                "id": plan.get("id"),
                "summary": plan.get("summary"),
                "recommendations": plan.get("recommendations", []),
                "monthly_target_savings": plan.get("monthly_target_savings", 0),
                "generated_at": plan.get("generated_at"),
                "is_active": plan.get("is_active", True),
                "goal_ids": plan.get("goal_ids", [])
            }
        })
    
    except ValidationError as e:
        return bad_request(e.message)
    except Exception as e:
        logger.error(f"Error creating plan: {str(e)}")
        return internal_error("Failed to create plan")
