"""
POST /chat/suggest-goals
Get AI-suggested goals based on transaction history.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Any, Dict, List

import boto3

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, bad_request, internal_error, service_unavailable
from shared.auth import require_auth
from shared.database import AccountRepository, TransactionRepository, GoalRepository
from shared.validation import parse_body, validate_date

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Bedrock configuration
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

bedrock_runtime = boto3.client("bedrock-runtime")


def analyze_transactions(user_id: str, start_date: str, end_date: str) -> Dict:
    """Analyze user's transaction patterns."""
    account_repo = AccountRepository()
    txn_repo = TransactionRepository()
    
    accounts = account_repo.get_user_accounts(user_id)
    
    total_income = 0
    total_expenses = 0
    category_spending = defaultdict(float)
    monthly_income = []
    monthly_expenses = []
    
    for account in accounts:
        account_id = account.get("id")
        if not account_id:
            continue
        
        transactions = txn_repo.get_account_transactions(user_id, account_id, limit=500)
        
        for txn in transactions:
            txn_date = txn.get("date", "")[:10]
            
            if not (start_date <= txn_date <= end_date):
                continue
            
            amount = txn.get("amount", 0)
            category = txn.get("category_name", "Other")
            
            if amount >= 0:
                total_income += amount
            else:
                total_expenses += abs(amount)
                category_spending[category] += abs(amount)
    
    # Calculate averages
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        months = max(1, (end - start).days / 30)
    except ValueError:
        months = 6
    
    avg_monthly_income = total_income / months
    avg_monthly_expenses = total_expenses / months
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "avg_monthly_income": avg_monthly_income,
        "avg_monthly_expenses": avg_monthly_expenses,
        "category_spending": dict(category_spending),
        "months_analyzed": months
    }


def call_bedrock_for_goals(analysis: Dict, existing_goals: List[Dict]) -> List[Dict]:
    """Call Bedrock to suggest goals based on transaction analysis."""
    existing_goal_titles = [g.get("title", "").lower() for g in existing_goals]
    
    system_prompt = f"""You are a financial advisor AI. Based on the user's spending analysis, suggest 2-3 personalized financial goals.

Transaction Analysis:
- Average monthly income: ${analysis['avg_monthly_income']:,.2f}
- Average monthly expenses: ${analysis['avg_monthly_expenses']:,.2f}
- Months analyzed: {analysis['months_analyzed']:.0f}
- Top spending categories: {json.dumps(dict(sorted(analysis['category_spending'].items(), key=lambda x: x[1], reverse=True)[:5]))}

Existing goals (avoid duplicates): {existing_goal_titles}

Suggest goals that are:
1. Specific and measurable
2. Achievable based on their income/expense ratio
3. Varied (emergency fund, debt payoff, savings, etc.)

Respond in this exact JSON format:
{{
    "suggested_goals": [
        {{
            "title": "Goal Title",
            "description": "Brief description of why this goal matters",
            "target_amount": 5000,
            "suggested_target_date": "YYYY-MM-DD",
            "category": "emergency|savings|debt_payoff|vacation|investment|purchase",
            "reasoning": "Explanation based on their finances"
        }}
    ]
}}
"""
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1500,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": "Based on my spending patterns, what financial goals should I set?"
            }
        ]
    }
    
    response = bedrock_runtime.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json"
    )
    
    response_body = json.loads(response["body"].read())
    response_text = response_body.get("content", [{}])[0].get("text", "{}")
    
    try:
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0]
        else:
            json_str = response_text
        
        result = json.loads(json_str.strip())
        return result.get("suggested_goals", [])
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse goals JSON: {response_text}")
        # Return default suggestions
        monthly_savings = analysis['avg_monthly_income'] - analysis['avg_monthly_expenses']
        emergency_fund = analysis['avg_monthly_expenses'] * 3
        
        return [
            {
                "title": "Emergency Fund",
                "description": "Build a 3-month safety net for unexpected expenses",
                "target_amount": round(emergency_fund, 2),
                "suggested_target_date": (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d"),
                "category": "emergency",
                "reasoning": f"Based on your monthly expenses of ${analysis['avg_monthly_expenses']:,.2f}, a 3-month emergency fund would be ${emergency_fund:,.2f}"
            }
        ]


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle suggest goals request."""
    try:
        user_id = event["user_id"]
        body = parse_body(event)
        
        # Get date range
        date_range = body.get("date_range", {})
        
        # Default to last 6 months if not provided
        if not date_range:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        else:
            start_date = date_range.get("start")
            end_date = date_range.get("end")
        
        # Validate dates
        if not start_date or not validate_date(start_date):
            return bad_request("Invalid start date format. Use YYYY-MM-DD")
        if not end_date or not validate_date(end_date):
            return bad_request("Invalid end date format. Use YYYY-MM-DD")
        
        # Analyze transactions
        analysis = analyze_transactions(user_id, start_date, end_date)
        
        # Get existing goals to avoid duplicates
        goal_repo = GoalRepository()
        existing_goals = goal_repo.get_user_goals(user_id, status="all")
        
        # Generate goal suggestions with AI
        try:
            suggested_goals = call_bedrock_for_goals(analysis, existing_goals)
        except Exception as e:
            logger.error(f"Bedrock call failed: {str(e)}")
            return service_unavailable("AI service temporarily unavailable")
        
        return success({
            "suggested_goals": suggested_goals
        })
    
    except Exception as e:
        logger.error(f"Error suggesting goals: {str(e)}")
        return internal_error("Failed to generate goal suggestions")
