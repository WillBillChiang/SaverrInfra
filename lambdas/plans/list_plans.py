"""
GET /plans
Get all financial plans (usually just the active one).
"""
import os
import logging
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, internal_error
from shared.auth import require_auth
from shared.database import PlanRepository
from shared.validation import get_query_param_bool

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle list plans request."""
    try:
        user_id = event["user_id"]
        
        # Parse query parameters
        active_only = get_query_param_bool(event, "active_only", default=True)
        
        repo = PlanRepository()
        plans = repo.get_user_plans(user_id, active_only=active_only)
        
        # Format response
        formatted_plans = []
        for plan in plans:
            formatted_plans.append({
                "id": plan.get("id"),
                "summary": plan.get("summary"),
                "recommendations": plan.get("recommendations", []),
                "monthly_target_savings": plan.get("monthly_target_savings", 0),
                "generated_at": plan.get("generated_at"),
                "is_active": plan.get("is_active", False)
            })
        
        return success({"plans": formatted_plans})
    
    except Exception as e:
        logger.error(f"Error listing plans: {str(e)}")
        return internal_error("Failed to retrieve plans")
