"""
GET /analytics/budget-comparison
Get budget vs actual spending comparison.
"""
import os
import logging
from collections import defaultdict
from typing import Any, Dict

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, bad_request, internal_error
from shared.auth import require_auth
from shared.database import AccountRepository, TransactionRepository, get_table
from shared.validation import get_query_param, validate_month

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Budget table
BUDGETS_TABLE = os.environ.get("BUDGETS_TABLE", "saverr-budgets")


def get_user_budget(user_id: str, month: str) -> Dict:
    """Get user's budget for a specific month."""
    try:
        table = get_table(BUDGETS_TABLE)
        response = table.get_item(
            Key={
                "pk": f"USER#{user_id}",
                "sk": f"BUDGET#{month}"
            }
        )
        return response.get("Item", {})
    except Exception as e:
        logger.warning(f"Error fetching budget: {str(e)}")
        return {}


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle budget comparison analytics request."""
    try:
        user_id = event["user_id"]
        
        # Parse query parameters
        month = get_query_param(event, "month")
        
        # Validate required parameters
        if not month:
            return bad_request("month is required (format: YYYY-MM)")
        
        if not validate_month(month):
            return bad_request("Invalid month format. Use YYYY-MM")
        
        # Get user's budget for this month
        budget = get_user_budget(user_id, month)
        budgeted_total = budget.get("total_budget", 0)
        category_budgets = budget.get("categories", {})
        
        # Get start and end dates for the month
        year, month_num = month.split("-")
        start_date = f"{month}-01"
        
        # Calculate end of month
        if month_num == "12":
            end_date = f"{int(year) + 1}-01-01"
        else:
            end_date = f"{year}-{int(month_num) + 1:02d}-01"
        
        # Get all user accounts
        account_repo = AccountRepository()
        accounts = account_repo.get_user_accounts(user_id)
        
        # Collect spending by category
        category_actual = defaultdict(float)
        txn_repo = TransactionRepository()
        
        for account in accounts:
            account_id = account.get("id")
            if account_id:
                transactions = txn_repo.get_account_transactions(
                    user_id,
                    account_id,
                    limit=1000
                )
                
                for txn in transactions:
                    txn_date = txn.get("date", "")[:10]
                    amount = txn.get("amount", 0)
                    
                    # Only count expenses (negative amounts)
                    if amount >= 0:
                        continue
                    
                    # Filter by date range
                    if not (start_date <= txn_date < end_date):
                        continue
                    
                    category = txn.get("category_name", "Other")
                    category_actual[category] += abs(amount)
        
        # Calculate totals
        actual_total = sum(category_actual.values())
        is_over_budget = actual_total > budgeted_total if budgeted_total > 0 else False
        percent_used = actual_total / budgeted_total if budgeted_total > 0 else 0
        
        # Build category comparison
        all_categories = set(category_budgets.keys()) | set(category_actual.keys())
        by_category = []
        
        for category_name in sorted(all_categories):
            cat_budgeted = category_budgets.get(category_name, 0)
            cat_actual = category_actual.get(category_name, 0)
            
            by_category.append({
                "category_name": category_name,
                "budgeted": round(cat_budgeted, 2),
                "actual": round(cat_actual, 2),
                "is_over_budget": cat_actual > cat_budgeted if cat_budgeted > 0 else False
            })
        
        return success({
            "budgeted": round(budgeted_total, 2),
            "actual": round(actual_total, 2),
            "is_over_budget": is_over_budget,
            "percent_used": round(percent_used, 4),
            "by_category": by_category
        })
    
    except Exception as e:
        logger.error(f"Error getting budget comparison: {str(e)}")
        return internal_error("Failed to retrieve budget comparison")
