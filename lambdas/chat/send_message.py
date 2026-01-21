"""
POST /chat/message
Send a message to the AI financial advisor using Amazon Bedrock.
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
    generate_id,
    get_timestamp
)
from shared.validation import parse_body, require_fields, sanitize_string

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Bedrock configuration
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

bedrock_runtime = boto3.client("bedrock-runtime")


def build_financial_context(user_id: str) -> str:
    """Build financial context string from user's data."""
    try:
        account_repo = AccountRepository()
        goal_repo = GoalRepository()

        accounts = account_repo.get_user_accounts(user_id)
        goals = goal_repo.get_user_goals(user_id, status="active")

        total_balance = sum(acc.get("balance", 0) for acc in accounts)

        context_parts = [
            f"User has {len(accounts)} linked accounts with total balance of ${total_balance:,.2f}."
        ]

        if accounts:
            account_summary = ", ".join([
                f"{acc.get('account_name', 'Account')} (${acc.get('balance', 0):,.2f})"
                for acc in accounts[:5]
            ])
            context_parts.append(f"Accounts: {account_summary}")

        if goals:
            goals_summary = ", ".join([
                f"{g.get('title', 'Goal')} (${g.get('current_amount', 0):,.2f}/${g.get('target_amount', 0):,.2f})"
                for g in goals[:5]
            ])
            context_parts.append(f"Active goals: {goals_summary}")

        return " ".join(context_parts)

    except Exception as e:
        logger.warning(f"Failed to build financial context: {str(e)}")
        return ""


def format_conversation_history(context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format conversation history for Bedrock Claude."""
    messages = []
    for msg in context:
        role = "user" if msg.get("is_from_user") else "assistant"
        content = msg.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    return messages


def call_bedrock(
    messages: List[Dict[str, Any]],
    system_prompt: str,
    user_message: str
) -> str:
    """Call Amazon Bedrock Claude model."""
    # Add user message to conversation
    messages.append({"role": "user", "content": user_message})

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
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
    return response_body.get("content", [{}])[0].get("text", "")


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle chat message request."""
    try:
        user_id = event["user_id"]
        body = parse_body(event)
        require_fields(body, ["message"])

        user_message = sanitize_string(body["message"], max_length=2000)
        conversation_context = body.get("context", [])
        include_financial_context = body.get("include_financial_context", True)

        if not user_message:
            return bad_request("Message cannot be empty")

        # Build system prompt
        system_prompt = """You are a helpful AI financial advisor for the Saverr app. Your role is to:
- Help users understand their finances and spending patterns
- Provide personalized budgeting advice
- Suggest ways to save money and reach financial goals
- Answer questions about personal finance in a friendly, accessible way

Guidelines:
- Be encouraging and supportive
- Give specific, actionable advice when possible
- Use the user's financial data when relevant
- Keep responses concise but informative
- Never give specific investment recommendations
- Remind users to consult professionals for complex financial decisions

"""

        # Add financial context if requested
        if include_financial_context:
            financial_context = build_financial_context(user_id)
            if financial_context:
                system_prompt += f"\n\nUser's financial context: {financial_context}"

        # Format conversation history
        messages = format_conversation_history(conversation_context[-10:])  # Last 10 messages

        # Call Bedrock
        try:
            ai_response = call_bedrock(messages, system_prompt, user_message)
        except Exception as e:
            logger.error(f"Bedrock API error: {str(e)}")
            return service_unavailable("AI service temporarily unavailable. Please try again.")

        # Generate suggestions based on the response
        suggestions = []
        response_lower = ai_response.lower()
        if "budget" in response_lower or "spending" in response_lower:
            suggestions.append("Create a budget")
        if "save" in response_lower or "saving" in response_lower:
            suggestions.append("Set a savings goal")
        if "transaction" in response_lower or "expense" in response_lower:
            suggestions.append("Review my spending")
        if not suggestions:
            suggestions = ["Tell me more", "Set a goal", "Check my accounts"]

        return success({
            "response": {
                "id": generate_id(),
                "content": ai_response,
                "timestamp": get_timestamp(),
                "message_type": "text",
                "suggestions": suggestions[:3]
            }
        })

    except Exception as e:
        logger.error(f"Chat message error: {str(e)}")
        if hasattr(e, "message"):
            return bad_request(e.message)
        return internal_error("Failed to process message")
