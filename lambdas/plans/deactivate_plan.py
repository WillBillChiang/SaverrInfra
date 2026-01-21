"""
PUT /plans/{plan_id}/deactivate
Deactivate a financial plan.
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, not_found, bad_request, internal_error
from shared.auth import require_auth
from shared.database import PlanRepository
from shared.validation import get_path_param, validate_uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle deactivate plan request."""
    try:
        user_id = event["user_id"]
        plan_id = get_path_param(event, "plan_id")
        
        if not plan_id:
            return bad_request("Plan ID is required")
        
        if not validate_uuid(plan_id):
            return bad_request("Invalid plan ID format")
        
        repo = PlanRepository()
        
        # Verify plan exists (get all plans including inactive)
        plans = repo.get_user_plans(user_id, active_only=False)
        plan = next((p for p in plans if p.get("id") == plan_id), None)
        
        if not plan:
            return not_found("Plan not found")
        
        # Deactivate the plan
        repo.deactivate_plan(user_id, plan_id)
        
        return success({
            "success": True,
            "message": "Plan deactivated"
        })
    
    except Exception as e:
        logger.error(f"Error deactivating plan: {str(e)}")
        return internal_error("Failed to deactivate plan")
