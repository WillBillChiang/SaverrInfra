"""
GET /analytics/cash-flow
Get cash flow data for visualizations.
"""
import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Any, Dict, List

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, bad_request, internal_error
from shared.auth import require_auth
from shared.database import AccountRepository, TransactionRepository
from shared.validation import get_query_param, validate_date, validate_enum, ValidationError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def aggregate_by_granularity(transactions: List[Dict], granularity: str) -> tuple:
    """Aggregate transactions by granularity (daily, weekly, monthly)."""
    inflows = defaultdict(float)
    outflows = defaultdict(float)
    
    for txn in transactions:
        amount = txn.get("amount", 0)
        date_str = txn.get("date", "")[:10]  # Get just the date part
        
        if not date_str:
            continue
        
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        
        # Determine the period key based on granularity
        if granularity == "daily":
            key = date_str
        elif granularity == "weekly":
            # Get the Monday of the week
            week_start = date - timedelta(days=date.weekday())
            key = week_start.strftime("%Y-%m-%d")
        else:  # monthly
            key = date.strftime("%Y-%m")
        
        if amount >= 0:
            inflows[key] += amount
        else:
            outflows[key] += abs(amount)
    
    return inflows, outflows


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle cash flow analytics request."""
    try:
        user_id = event["user_id"]
        
        # Parse query parameters
        start_date = get_query_param(event, "start_date")
        end_date = get_query_param(event, "end_date")
        granularity = get_query_param(event, "granularity", default="daily")
        
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
        
        # Validate granularity
        try:
            validate_enum(granularity, ["daily", "weekly", "monthly"], "granularity")
        except ValidationError as e:
            return bad_request(e.message)
        
        # Get all user accounts
        account_repo = AccountRepository()
        accounts = account_repo.get_user_accounts(user_id)
        
        # Collect all transactions from all accounts
        all_transactions = []
        txn_repo = TransactionRepository()
        
        for account in accounts:
            account_id = account.get("id")
            if account_id:
                transactions = txn_repo.get_account_transactions(
                    user_id,
                    account_id,
                    limit=1000
                )
                # Filter by date range
                for txn in transactions:
                    txn_date = txn.get("date", "")[:10]
                    if start_date <= txn_date <= end_date:
                        all_transactions.append(txn)
        
        # Aggregate by granularity
        inflows, outflows = aggregate_by_granularity(all_transactions, granularity)
        
        # Format response
        inflow_list = [{"date": k, "amount": round(v, 2)} for k, v in sorted(inflows.items())]
        outflow_list = [{"date": k, "amount": round(v, 2)} for k, v in sorted(outflows.items())]
        
        total_inflow = sum(inflows.values())
        total_outflow = sum(outflows.values())
        net_flow = total_inflow - total_outflow
        
        return success({
            "inflows": inflow_list,
            "outflows": outflow_list,
            "net_flow": round(net_flow, 2),
            "total_inflow": round(total_inflow, 2),
            "total_outflow": round(total_outflow, 2)
        })
    
    except Exception as e:
        logger.error(f"Error getting cash flow: {str(e)}")
        return internal_error("Failed to retrieve cash flow data")
