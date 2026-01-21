"""
POST /chat/generate-plan
Generate a personalized financial plan based on chat context.
"""
import os
import json
import logging
from typing import Any, Dict, List

import boto3

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, bad_request, internal_error, service_unavailable
from shared.auth import require_auth
from shared.database import (
    AccountRepository,
    TransactionRepository,
    GoalRepository,
    PlanRepository,
    generate_id,
    get_timestamp
)
from shared.validation import parse_body, get_query_param_int, sanitize_string

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Bedrock configuration
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

bedrock_runtime = boto3.client("bedrock-runtime")


def build_financial_context(user_id: str, include_transactions: bool = True) -> str:
    """Build comprehensive financial context for plan generation."""
    try:
        account_repo = AccountRepository()
        goal_repo = GoalRepository()
        
        accounts = account_repo.get_user_accounts(user_id)
        goals = goal_repo.get_user_goals(user_id, status="active")
        
        total_balance = sum(acc.get("balance", 0) for acc in accounts)
        
        context_parts = [
            f"Total balance across {len(accounts)} accounts: ${total_balance:,.2f}",
        ]
        
        # Add account details
        for acc in accounts[:5]:
            context_parts.append(
                f"- {acc.get('account_name')}: ${acc.get('balance', 0):,.2f} ({acc.get('account_type')})"
            )
        
        # Add goal details
        if goals:
            context_parts.append(f"\nActive goals ({len(goals)}):")
            for g in goals[:5]:
                progress = g.get('progress', 0) * 100
                context_parts.append(
                    f"- {g.get('title')}: ${g.get('current_amount', 0):,.2f}/${g.get('target_amount', 0):,.2f} ({progress:.0f}%)"
                )
        
        # Add recent spending summary if requested
        if include_transactions:
            txn_repo = TransactionRepository()
            recent_spending = 0
            for acc in accounts[:3]:
                account_id = acc.get("id")
                if account_id:
                    txns = txn_repo.get_account_transactions(user_id, account_id, limit=50)
                    for txn in txns:
                        if txn.get("amount", 0) < 0:
                            recent_spending += abs(txn.get("amount", 0))
            
            context_parts.append(f"\nRecent spending (approx): ${recent_spending:,.2f}")
        
        return "\n".join(context_parts)
    
    except Exception as e:
        logger.warning(f"Failed to build financial context: {str(e)}")
        return ""


def call_bedrock_for_plan(context: str, chat_context: List[Dict], time_horizon: int) -> Dict:
    """Call Bedrock to generate a financial plan."""
    system_prompt = f"""You are a financial planning AI assistant. Generate a personalized financial plan based on the user's conversation and financial data.

The plan should include:
1. A clear summary of the plan (2-3 sentences)
2. 3-5 specific, actionable recommendations
3. A suggested monthly savings target based on their situation
4. 1-3 suggested goals if appropriate

Financial Context:
{context}

Time horizon: {time_horizon} months

Respond in this exact JSON format:
{{
    "summary": "Plan summary here...",
    "recommendations": ["Recommendation 1", "Recommendation 2", "Recommendation 3"],
    "monthly_target_savings": 500,
    "suggested_goals": [
        {{
            "title": "Goal Title",
            "target_amount": 5000,
            "target_date": "YYYY-MM-DD",
            "category": "emergency|savings|vacation|debt_payoff|investment|purchase",
            "priority": 1
        }}
    ]
}}
"""
    
    # Format chat history
    messages = []
    for msg in chat_context[-10:]:
        role = "user" if msg.get("is_from_user") else "assistant"
        content = msg.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    
    # Add final instruction
    messages.append({
        "role": "user",
        "content": "Based on our conversation and my financial situation, please generate a personalized financial plan in the JSON format specified."
    })
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "system": system_prompt,
        "messages": messages
    }
    
    response = bedrock_runtime.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json"
    )
    
    response_body = json.loads(response["body"].read())
    response_text = response_body.get("content", [{}])[0].get("text", "{}")
    
    # Parse the JSON response
    try:
        # Try to extract JSON from the response
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0]
        else:
            json_str = response_text
        
        return json.loads(json_str.strip())
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse plan JSON: {response_text}")
        return {
            "summary": "Based on your financial situation, here's a personalized plan.",
            "recommendations": [
                "Build an emergency fund covering 3-6 months of expenses",
                "Review and reduce unnecessary subscriptions",
                "Set up automatic savings transfers"
            ],
            "monthly_target_savings": 300,
            "suggested_goals": []
        }


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle generate plan request."""
    try:
        user_id = event["user_id"]
        body = parse_body(event)
        
        chat_context = body.get("context", [])
        include_transactions = body.get("include_transactions", True)
        time_horizon = body.get("time_horizon_months", 12)
        
        # Validate time horizon
        if not isinstance(time_horizon, int) or time_horizon < 1 or time_horizon > 120:
            time_horizon = 12
        
        # Build financial context
        financial_context = build_financial_context(user_id, include_transactions)
        
        # Generate plan with AI
        try:
            plan_data = call_bedrock_for_plan(financial_context, chat_context, time_horizon)
        except Exception as e:
            logger.error(f"Bedrock call failed: {str(e)}")
            return service_unavailable("AI service temporarily unavailable")
        
        # Save the plan
        plan_repo = PlanRepository()
        
        # Deactivate existing plans
        existing_plans = plan_repo.get_user_plans(user_id, active_only=True)
        for existing in existing_plans:
            plan_repo.deactivate_plan(user_id, existing.get("id"))
        
        plan = plan_repo.create_plan(user_id, {
            "summary": plan_data.get("summary", ""),
            "recommendations": plan_data.get("recommendations", []),
            "monthly_target_savings": plan_data.get("monthly_target_savings", 0),
            "is_active": True
        })
        
        # Format suggested goals
        suggested_goals = []
        for goal in plan_data.get("suggested_goals", []):
            suggested_goals.append({
                "title": goal.get("title", ""),
                "target_amount": goal.get("target_amount", 0),
                "target_date": goal.get("target_date", ""),
                "category": goal.get("category", "savings"),
                "priority": goal.get("priority", 0)
            })
        
        return success({
            "plan": {
                "id": plan.get("id"),
                "summary": plan.get("summary"),
                "recommendations": plan.get("recommendations", []),
                "monthly_target_savings": plan.get("monthly_target_savings", 0),
                "generated_at": plan.get("generated_at"),
                "is_active": True,
                "suggested_goals": suggested_goals
            }
        })
    
    except Exception as e:
        logger.error(f"Error generating plan: {str(e)}")
        return internal_error("Failed to generate financial plan")
