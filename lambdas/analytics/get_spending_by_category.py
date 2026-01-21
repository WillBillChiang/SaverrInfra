"""
GET /analytics/spending-by-category
Get spending breakdown by category.
"""
import os
import logging
from collections import defaultdict
from typing import Any, Dict, List

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, bad_request, internal_error
from shared.auth import require_auth
from shared.database import AccountRepository, TransactionRepository
from shared.validation import get_query_param, validate_date

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Category configuration
CATEGORY_CONFIG = {
    "Food & Dining": {"icon_name": "fork.knife", "color_hex": "#FF6B6B"},
    "Shopping": {"icon_name": "bag", "color_hex": "#4ECDC4"},
    "Transportation": {"icon_name": "car", "color_hex": "#45B7D1"},
    "Entertainment": {"icon_name": "film", "color_hex": "#96CEB4"},
    "Bills & Utilities": {"icon_name": "doc.text", "color_hex": "#FFEAA7"},
    "Health": {"icon_name": "heart", "color_hex": "#FF8A5B"},
    "Travel": {"icon_name": "airplane", "color_hex": "#A8E6CF"},
    "Education": {"icon_name": "book", "color_hex": "#DDA0DD"},
    "Personal Care": {"icon_name": "person", "color_hex": "#FFB6C1"},
    "Other": {"icon_name": "ellipsis.circle", "color_hex": "#B0B0B0"}
}


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle spending by category analytics request."""
    try:
        user_id = event["user_id"]
        
        # Parse query parameters
        start_date = get_query_param(event, "start_date")
        end_date = get_query_param(event, "end_date")
        
        # Validate required parameters
        if not start_date:
            return bad_request("start_date is required")
        if not end_date:
            return bad_request("end_date is required")
        
        # Validate date formats
        if not validate_date(start_date):
            return bad_request("Invalid start_date format. Use YYYY-MM-DD")
        if not validate_date(end_date):
            return bad_request("Invalid end_date format. Use YYYY-MM-DD")
        
        # Get all user accounts
        account_repo = AccountRepository()
        accounts = account_repo.get_user_accounts(user_id)
        
        # Collect spending transactions by category
        category_spending = defaultdict(lambda: {"amount": 0, "count": 0})
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
                    if not (start_date <= txn_date <= end_date):
                        continue
                    
                    category = txn.get("category_name", "Other")
                    category_spending[category]["amount"] += abs(amount)
                    category_spending[category]["count"] += 1
        
        # Calculate total spending
        total_spending = sum(cat["amount"] for cat in category_spending.values())
        
        # Format response
        categories = []
        for category_name, data in sorted(category_spending.items(), 
                                          key=lambda x: x[1]["amount"], 
                                          reverse=True):
            config = CATEGORY_CONFIG.get(category_name, CATEGORY_CONFIG["Other"])
            percentage = data["amount"] / total_spending if total_spending > 0 else 0
            
            categories.append({
                "category_name": category_name,
                "icon_name": config["icon_name"],
                "color_hex": config["color_hex"],
                "amount": round(data["amount"], 2),
                "percentage": round(percentage, 4),
                "transaction_count": data["count"]
            })
        
        return success({
            "categories": categories,
            "total_spending": round(total_spending, 2)
        })
    
    except Exception as e:
        logger.error(f"Error getting spending by category: {str(e)}")
        return internal_error("Failed to retrieve spending data")
