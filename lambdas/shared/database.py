"""
Database utilities for DynamoDB operations.
Provides common database operations and table name resolution.
"""
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")

# Table names from environment variables
USERS_TABLE = os.environ.get("USERS_TABLE", "saverr-users")
ACCOUNTS_TABLE = os.environ.get("ACCOUNTS_TABLE", "saverr-accounts")
TRANSACTIONS_TABLE = os.environ.get("TRANSACTIONS_TABLE", "saverr-transactions")
GOALS_TABLE = os.environ.get("GOALS_TABLE", "saverr-goals")
PLANS_TABLE = os.environ.get("PLANS_TABLE", "saverr-plans")
CHAT_HISTORY_TABLE = os.environ.get("CHAT_HISTORY_TABLE", "saverr-chat-history")


def get_table(table_name: str):
    """Get a DynamoDB table resource."""
    return dynamodb.Table(table_name)


def generate_id() -> str:
    """Generate a new UUID."""
    return str(uuid.uuid4())


def get_timestamp() -> str:
    """Get current ISO 8601 timestamp."""
    return datetime.utcnow().isoformat() + "Z"


def decimal_to_float(obj: Any) -> Any:
    """Convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


def float_to_decimal(obj: Any) -> Any:
    """Convert float values to Decimal for DynamoDB storage."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(item) for item in obj]
    return obj


class BaseRepository:
    """Base class for DynamoDB repository operations."""

    def __init__(self, table_name: str):
        self.table = get_table(table_name)
        self.table_name = table_name

    def get_by_id(self, pk: str, sk: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get an item by primary key."""
        key = {"pk": pk}
        if sk is not None:
            key["sk"] = sk

        response = self.table.get_item(Key=key)
        item = response.get("Item")
        return decimal_to_float(item) if item else None

    def put(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Put an item into the table."""
        item = float_to_decimal(item)
        self.table.put_item(Item=item)
        return decimal_to_float(item)

    def update(
        self,
        pk: str,
        sk: Optional[str],
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an item with the given attributes."""
        key = {"pk": pk}
        if sk is not None:
            key["sk"] = sk

        updates = float_to_decimal(updates)
        update_expression_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}

        for i, (attr, value) in enumerate(updates.items()):
            placeholder = f"#attr{i}"
            value_placeholder = f":val{i}"
            update_expression_parts.append(f"{placeholder} = {value_placeholder}")
            expression_attribute_names[placeholder] = attr
            expression_attribute_values[value_placeholder] = value

        response = self.table.update_item(
            Key=key,
            UpdateExpression="SET " + ", ".join(update_expression_parts),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW"
        )

        return decimal_to_float(response.get("Attributes", {}))

    def delete(self, pk: str, sk: Optional[str] = None) -> bool:
        """Delete an item by primary key."""
        key = {"pk": pk}
        if sk is not None:
            key["sk"] = sk

        self.table.delete_item(Key=key)
        return True

    def query_by_pk(
        self,
        pk: str,
        sk_prefix: Optional[str] = None,
        limit: Optional[int] = None,
        scan_forward: bool = True
    ) -> List[Dict[str, Any]]:
        """Query items by partition key with optional sort key prefix."""
        key_condition = Key("pk").eq(pk)
        if sk_prefix:
            key_condition = key_condition & Key("sk").begins_with(sk_prefix)

        params = {
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_forward
        }
        if limit:
            params["Limit"] = limit

        response = self.table.query(**params)
        items = response.get("Items", [])
        return [decimal_to_float(item) for item in items]

    def query_gsi(
        self,
        index_name: str,
        pk_name: str,
        pk_value: str,
        sk_name: Optional[str] = None,
        sk_value: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query a Global Secondary Index."""
        key_condition = Key(pk_name).eq(pk_value)
        if sk_name and sk_value:
            key_condition = key_condition & Key(sk_name).eq(sk_value)

        params = {
            "IndexName": index_name,
            "KeyConditionExpression": key_condition
        }
        if limit:
            params["Limit"] = limit

        response = self.table.query(**params)
        items = response.get("Items", [])
        return [decimal_to_float(item) for item in items]


class AccountRepository(BaseRepository):
    """Repository for account operations."""

    def __init__(self):
        super().__init__(ACCOUNTS_TABLE)

    def get_user_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all accounts for a user."""
        return self.query_by_pk(f"USER#{user_id}", "ACCOUNT#")

    def get_account(self, user_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific account."""
        return self.get_by_id(f"USER#{user_id}", f"ACCOUNT#{account_id}")

    def create_account(self, user_id: str, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new account."""
        account_id = generate_id()
        item = {
            "pk": f"USER#{user_id}",
            "sk": f"ACCOUNT#{account_id}",
            "id": account_id,
            "user_id": user_id,
            "created_at": get_timestamp(),
            "last_updated": get_timestamp(),
            **account_data
        }
        return self.put(item)

    def delete_account(self, user_id: str, account_id: str) -> bool:
        """Delete an account."""
        return self.delete(f"USER#{user_id}", f"ACCOUNT#{account_id}")


class TransactionRepository(BaseRepository):
    """Repository for transaction operations."""

    def __init__(self):
        super().__init__(TRANSACTIONS_TABLE)

    def get_account_transactions(
        self,
        user_id: str,
        account_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get transactions for an account."""
        # Query with pagination
        transactions = self.query_by_pk(
            f"ACCOUNT#{account_id}",
            "TXN#",
            limit=limit + offset,
            scan_forward=False  # Most recent first
        )
        return transactions[offset:offset + limit]


class GoalRepository(BaseRepository):
    """Repository for goal operations."""

    def __init__(self):
        super().__init__(GOALS_TABLE)

    def get_user_goals(self, user_id: str, status: str = "active") -> List[Dict[str, Any]]:
        """Get all goals for a user."""
        goals = self.query_by_pk(f"USER#{user_id}", "GOAL#")
        if status != "all":
            goals = [g for g in goals if g.get("status", "active") == status]
        return goals

    def get_goal(self, user_id: str, goal_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific goal."""
        return self.get_by_id(f"USER#{user_id}", f"GOAL#{goal_id}")

    def create_goal(self, user_id: str, goal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new goal."""
        goal_id = generate_id()
        current_amount = goal_data.get("current_amount", 0)
        target_amount = goal_data.get("target_amount", 1)
        progress = current_amount / target_amount if target_amount > 0 else 0

        item = {
            "pk": f"USER#{user_id}",
            "sk": f"GOAL#{goal_id}",
            "id": goal_id,
            "user_id": user_id,
            "created_at": get_timestamp(),
            "status": "active",
            "is_ai_generated": goal_data.get("is_ai_generated", False),
            "progress": progress,
            **goal_data
        }
        return self.put(item)

    def update_goal(self, user_id: str, goal_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a goal."""
        updates["last_updated"] = get_timestamp()

        # Recalculate progress if amounts changed
        if "current_amount" in updates or "target_amount" in updates:
            goal = self.get_goal(user_id, goal_id)
            if goal:
                current = updates.get("current_amount", goal.get("current_amount", 0))
                target = updates.get("target_amount", goal.get("target_amount", 1))
                updates["progress"] = current / target if target > 0 else 0

        return self.update(f"USER#{user_id}", f"GOAL#{goal_id}", updates)

    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        """Delete a goal."""
        return self.delete(f"USER#{user_id}", f"GOAL#{goal_id}")


class PlanRepository(BaseRepository):
    """Repository for financial plan operations."""

    def __init__(self):
        super().__init__(PLANS_TABLE)

    def get_user_plans(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all plans for a user."""
        plans = self.query_by_pk(f"USER#{user_id}", "PLAN#")
        if active_only:
            plans = [p for p in plans if p.get("is_active", False)]
        return plans

    def create_plan(self, user_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new plan."""
        plan_id = generate_id()
        item = {
            "pk": f"USER#{user_id}",
            "sk": f"PLAN#{plan_id}",
            "id": plan_id,
            "user_id": user_id,
            "generated_at": get_timestamp(),
            "is_active": True,
            **plan_data
        }
        return self.put(item)

    def deactivate_plan(self, user_id: str, plan_id: str) -> Dict[str, Any]:
        """Deactivate a plan."""
        return self.update(f"USER#{user_id}", f"PLAN#{plan_id}", {"is_active": False})
