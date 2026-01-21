"""
GET /analytics/savings-progress
Get progress on all savings goals.
"""
import os
import logging
from datetime import datetime
from typing import Any, Dict, List

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, internal_error
from shared.auth import require_auth
from shared.database import GoalRepository

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def calculate_projected_completion(goal: Dict) -> tuple:
    """Calculate projected completion date and if on track."""
    current_amount = goal.get("current_amount", 0)
    target_amount = goal.get("target_amount", 0)
    target_date = goal.get("target_date")
    created_at = goal.get("created_at", "")
    
    if not target_date or target_amount <= 0:
        return None, False, 0
    
    # Parse dates
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d")
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now()
    except (ValueError, TypeError):
        return None, False, 0
    
    # Calculate progress made so far
    remaining = target_amount - current_amount
    if remaining <= 0:
        return target_date, True, current_amount / (target - created).days if target > created else 0
    
    # Calculate days elapsed since creation
    days_elapsed = (now - created.replace(tzinfo=None)).days
    if days_elapsed <= 0:
        return target_date, True, 0
    
    # Calculate daily savings rate
    daily_rate = current_amount / days_elapsed if days_elapsed > 0 else 0
    
    # Calculate days remaining until target
    days_to_target = (target - now).days
    if days_to_target <= 0:
        return target_date, False, daily_rate * 30  # Monthly rate
    
    # Project completion
    if daily_rate > 0:
        days_to_complete = remaining / daily_rate
        projected_date = now + timedelta(days=int(days_to_complete))
        on_track = projected_date <= target
        projected_date_str = projected_date.strftime("%Y-%m-%d")
    else:
        projected_date_str = None
        on_track = False
    
    monthly_contribution = daily_rate * 30  # Approximate monthly contribution
    
    return projected_date_str, on_track, monthly_contribution


# Need to import timedelta
from datetime import timedelta


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle savings progress analytics request."""
    try:
        user_id = event["user_id"]
        
        # Get active goals
        repo = GoalRepository()
        goals = repo.get_user_goals(user_id, status="active")
        
        # Calculate progress for each goal
        goal_progress = []
        total_saved = 0
        total_target = 0
        
        for goal in goals:
            current_amount = goal.get("current_amount", 0)
            target_amount = goal.get("target_amount", 0)
            
            total_saved += current_amount
            total_target += target_amount
            
            projected_date, on_track, monthly_contribution = calculate_projected_completion(goal)
            
            goal_progress.append({
                "goal": {
                    "id": goal.get("id"),
                    "title": goal.get("title"),
                    "target_amount": target_amount,
                    "current_amount": current_amount,
                    "target_date": goal.get("target_date"),
                    "progress": goal.get("progress", 0)
                },
                "monthly_contribution": round(monthly_contribution, 2),
                "projected_completion_date": projected_date,
                "on_track": on_track
            })
        
        # Calculate overall progress
        overall_progress = total_saved / total_target if total_target > 0 else 0
        
        return success({
            "goals": goal_progress,
            "total_saved": round(total_saved, 2),
            "total_target": round(total_target, 2),
            "overall_progress": round(overall_progress, 4)
        })
    
    except Exception as e:
        logger.error(f"Error getting savings progress: {str(e)}")
        return internal_error("Failed to retrieve savings progress")
