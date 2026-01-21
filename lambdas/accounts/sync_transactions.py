"""
POST /accounts/{account_id}/sync
Sync transactions from Plaid for a specific account.
This fetches transactions from Plaid API and stores them in DynamoDB.

Plaid API Reference: https://plaid.com/docs/api/products/transactions/#transactionssync
"""
import os
import logging
import json
import urllib.request
from typing import Any, Dict, List
from datetime import datetime, timedelta

import boto3

# Add shared module to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success, not_found, bad_request, internal_error, service_unavailable
from shared.auth import require_auth
from shared.database import AccountRepository, TransactionRepository, get_timestamp, generate_id
from shared.validation import get_path_param, get_query_param, validate_uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Plaid configuration
PLAID_SECRET_ARN = os.environ.get("PLAID_SECRET_ARN", "")

secrets_client = boto3.client("secretsmanager")


def get_plaid_credentials() -> Dict[str, str]:
    """Retrieve Plaid API credentials from Secrets Manager."""
    if not PLAID_SECRET_ARN:
        raise ValueError("Plaid secret ARN not configured")

    response = secrets_client.get_secret_value(SecretId=PLAID_SECRET_ARN)
    return json.loads(response["SecretString"])


def get_plaid_host(environment: str) -> str:
    """Get the Plaid API host for the given environment."""
    hosts = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com"
    }
    return hosts.get(environment, "https://sandbox.plaid.com")


def sync_transactions_from_plaid(
    access_token: str,
    plaid_creds: Dict[str, str],
    cursor: str = None,
    count: int = 100
) -> Dict[str, Any]:
    """
    Sync transactions using Plaid's /transactions/sync endpoint.
    This is the recommended method for getting transaction updates.
    
    Args:
        access_token: Plaid access token for the account
        plaid_creds: Plaid API credentials
        cursor: Pagination cursor for incremental syncs
        count: Number of transactions to fetch per request (max 500)
    
    Returns:
        Plaid sync response with added, modified, and removed transactions
    """
    plaid_host = get_plaid_host(plaid_creds.get("environment", "sandbox"))

    payload = {
        "client_id": plaid_creds["client_id"],
        "secret": plaid_creds["secret"],
        "access_token": access_token,
        "count": min(count, 500)
    }

    if cursor:
        payload["cursor"] = cursor

    req = urllib.request.Request(
        f"{plaid_host}/transactions/sync",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode())


def get_transactions_legacy(
    access_token: str,
    plaid_creds: Dict[str, str],
    start_date: str,
    end_date: str,
    account_ids: List[str] = None
) -> Dict[str, Any]:
    """
    Get transactions using the legacy /transactions/get endpoint.
    Use this as a fallback or for initial historical sync.
    
    Args:
        access_token: Plaid access token
        plaid_creds: Plaid API credentials
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        account_ids: Optional list of Plaid account IDs to filter
    
    Returns:
        Plaid transactions response
    """
    plaid_host = get_plaid_host(plaid_creds.get("environment", "sandbox"))

    payload = {
        "client_id": plaid_creds["client_id"],
        "secret": plaid_creds["secret"],
        "access_token": access_token,
        "start_date": start_date,
        "end_date": end_date,
        "options": {
            "count": 500,
            "offset": 0,
            "include_personal_finance_category": True
        }
    }

    if account_ids:
        payload["options"]["account_ids"] = account_ids

    req = urllib.request.Request(
        f"{plaid_host}/transactions/get",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode())


def map_plaid_transaction(plaid_txn: Dict[str, Any], user_id: str, account_id: str) -> Dict[str, Any]:
    """
    Map a Plaid transaction to our internal format.
    
    Args:
        plaid_txn: Transaction from Plaid API
        user_id: User ID
        account_id: Our internal account ID
    
    Returns:
        Transaction in our database format
    """
    # Get personal finance category if available
    pfc = plaid_txn.get("personal_finance_category", {})
    category_name = pfc.get("primary", plaid_txn.get("category", ["Uncategorized"])[0] if plaid_txn.get("category") else "Uncategorized")
    category_detailed = pfc.get("detailed", "")

    # Map category to icon and color
    category_icons = {
        "FOOD_AND_DRINK": ("fork.knife", "#FF6B6B"),
        "TRANSPORTATION": ("car.fill", "#4ECDC4"),
        "SHOPPING": ("bag.fill", "#45B7D1"),
        "ENTERTAINMENT": ("tv.fill", "#96CEB4"),
        "TRAVEL": ("airplane", "#FFEAA7"),
        "HEALTHCARE": ("heart.fill", "#DDA0DD"),
        "PERSONAL_CARE": ("person.fill", "#98D8C8"),
        "GENERAL_SERVICES": ("wrench.fill", "#F7DC6F"),
        "GOVERNMENT_AND_NON_PROFIT": ("building.columns.fill", "#BB8FCE"),
        "TRANSFER_IN": ("arrow.down.circle.fill", "#82E0AA"),
        "TRANSFER_OUT": ("arrow.up.circle.fill", "#F1948A"),
        "INCOME": ("dollarsign.circle.fill", "#82E0AA"),
        "LOAN_PAYMENTS": ("creditcard.fill", "#F5B041"),
        "BANK_FEES": ("exclamationmark.circle.fill", "#E74C3C"),
        "RENT_AND_UTILITIES": ("house.fill", "#5DADE2"),
    }

    icon, color = category_icons.get(category_name.upper(), ("questionmark.circle.fill", "#95A5A6"))

    return {
        "pk": f"ACCOUNT#{account_id}",
        "sk": f"TXN#{plaid_txn.get('transaction_id', generate_id())}",
        "id": plaid_txn.get("transaction_id", generate_id()),
        "user_id": user_id,
        "account_id": account_id,
        "plaid_transaction_id": plaid_txn.get("transaction_id"),
        "amount": abs(plaid_txn.get("amount", 0)),  # Plaid uses negative for debits
        "is_debit": plaid_txn.get("amount", 0) > 0,  # Plaid: positive = debit
        "description": plaid_txn.get("name", "Unknown Transaction"),
        "merchant_name": plaid_txn.get("merchant_name"),
        "date": plaid_txn.get("date"),
        "datetime": plaid_txn.get("datetime"),
        "pending": plaid_txn.get("pending", False),
        "category_name": category_name.replace("_", " ").title(),
        "category_detailed": category_detailed,
        "category_icon": icon,
        "category_color": color,
        "payment_channel": plaid_txn.get("payment_channel"),
        "location": {
            "city": plaid_txn.get("location", {}).get("city"),
            "region": plaid_txn.get("location", {}).get("region"),
            "country": plaid_txn.get("location", {}).get("country"),
        },
        "created_at": get_timestamp(),
        "synced_at": get_timestamp()
    }


@require_auth
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle transaction sync request.
    
    Query Parameters:
        - days: Number of days to sync (default: 30, max: 730 for legacy mode)
        - use_sync: Use /transactions/sync API (default: true)
    
    Response:
    {
        "synced": 150,
        "added": 145,
        "modified": 3,
        "removed": 2,
        "has_more": false,
        "cursor": "next_cursor_value"
    }
    """
    try:
        user_id = event["user_id"]
        account_id = get_path_param(event, "account_id")

        if not account_id:
            return bad_request("Account ID is required")

        if not validate_uuid(account_id):
            return bad_request("Invalid account ID format")

        # Get account
        account_repo = AccountRepository()
        account = account_repo.get_account(user_id, account_id)

        if not account:
            return not_found("Account not found")

        # Check for Plaid access token
        plaid_access_token = account.get("plaid_access_token")
        if not plaid_access_token:
            return bad_request("Account is not linked to Plaid")

        # Get Plaid credentials
        try:
            plaid_creds = get_plaid_credentials()
        except Exception as e:
            logger.error(f"Failed to get Plaid credentials: {str(e)}")
            return service_unavailable("Transaction sync service temporarily unavailable")

        # Determine sync method
        use_sync = get_query_param(event, "use_sync", "true").lower() == "true"
        days = int(get_query_param(event, "days", "30"))
        days = min(days, 730)  # Max 2 years

        txn_repo = TransactionRepository()
        stats = {"added": 0, "modified": 0, "removed": 0, "has_more": False, "cursor": None}

        if use_sync:
            # Use the modern /transactions/sync API
            cursor = account.get("plaid_sync_cursor")

            try:
                sync_response = sync_transactions_from_plaid(
                    plaid_access_token,
                    plaid_creds,
                    cursor=cursor
                )

                # Process added transactions
                for plaid_txn in sync_response.get("added", []):
                    if plaid_txn.get("account_id") == account.get("plaid_account_id"):
                        txn_data = map_plaid_transaction(plaid_txn, user_id, account_id)
                        txn_repo.put(txn_data)
                        stats["added"] += 1

                # Process modified transactions
                for plaid_txn in sync_response.get("modified", []):
                    if plaid_txn.get("account_id") == account.get("plaid_account_id"):
                        txn_data = map_plaid_transaction(plaid_txn, user_id, account_id)
                        txn_repo.put(txn_data)
                        stats["modified"] += 1

                # Process removed transactions
                for plaid_txn in sync_response.get("removed", []):
                    txn_id = plaid_txn.get("transaction_id")
                    if txn_id:
                        txn_repo.delete(f"ACCOUNT#{account_id}", f"TXN#{txn_id}")
                        stats["removed"] += 1

                # Save the new cursor
                new_cursor = sync_response.get("next_cursor")
                stats["has_more"] = sync_response.get("has_more", False)
                stats["cursor"] = new_cursor

                # Update account with new cursor
                account_repo.update(
                    f"USER#{user_id}",
                    f"ACCOUNT#{account_id}",
                    {
                        "plaid_sync_cursor": new_cursor,
                        "last_synced": get_timestamp()
                    }
                )

            except Exception as e:
                logger.error(f"Plaid sync failed: {str(e)}")
                return service_unavailable(f"Failed to sync transactions: {str(e)}")

        else:
            # Use legacy /transactions/get API
            end_date = datetime.utcnow().strftime("%Y-%m-%d")
            start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

            try:
                txn_response = get_transactions_legacy(
                    plaid_access_token,
                    plaid_creds,
                    start_date,
                    end_date,
                    account_ids=[account.get("plaid_account_id")]
                )

                for plaid_txn in txn_response.get("transactions", []):
                    txn_data = map_plaid_transaction(plaid_txn, user_id, account_id)
                    txn_repo.put(txn_data)
                    stats["added"] += 1

                # Update last synced
                account_repo.update(
                    f"USER#{user_id}",
                    f"ACCOUNT#{account_id}",
                    {"last_synced": get_timestamp()}
                )

            except Exception as e:
                logger.error(f"Plaid get transactions failed: {str(e)}")
                return service_unavailable(f"Failed to fetch transactions: {str(e)}")

        return success({
            "synced": stats["added"] + stats["modified"],
            "added": stats["added"],
            "modified": stats["modified"],
            "removed": stats["removed"],
            "has_more": stats["has_more"],
            "cursor": stats["cursor"]
        })

    except Exception as e:
        logger.error(f"Error syncing transactions: {str(e)}")
        return internal_error("Failed to sync transactions")
