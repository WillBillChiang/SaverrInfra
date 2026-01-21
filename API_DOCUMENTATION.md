# Saverr API Documentation

## Overview

This document describes all API endpoints that Saverr will use when connected to a real backend via API Gateway. Currently, all APIs are mocked locally using the mock service layer.

## Base URL

```
Production: https://api.saverr.app/v1
Staging: https://staging-api.saverr.app/v1
```

## Authentication

All endpoints require Bearer token authentication.

```
Authorization: Bearer <jwt_token>
```

### Authentication Endpoints

#### POST /auth/login
Authenticate a user and receive access tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

#### POST /auth/refresh
Refresh an expired access token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

## Banking APIs

### GET /accounts
Fetch all linked bank accounts for the authenticated user.

**Response:**
```json
{
  "accounts": [
    {
      "id": "uuid",
      "institution_name": "Chase",
      "account_name": "Total Checking",
      "account_type": "checking",
      "balance": 4523.67,
      "last_updated": "2026-01-21T10:30:00Z",
      "is_linked": true,
      "account_number_last4": "4521",
      "institution_logo": "building.columns"
    }
  ],
  "total_balance": 62818.01
}
```

### GET /accounts/{account_id}
Fetch details for a specific account.

**Path Parameters:**
- `account_id` (required): UUID of the account

**Response:**
```json
{
  "id": "uuid",
  "institution_name": "Chase",
  "account_name": "Total Checking",
  "account_type": "checking",
  "balance": 4523.67,
  "last_updated": "2026-01-21T10:30:00Z",
  "is_linked": true,
  "account_number_last4": "4521",
  "institution_logo": "building.columns",
  "routing_number_last4": "1234"
}
```

### GET /accounts/{account_id}/transactions
Fetch transactions for a specific account.

**Path Parameters:**
- `account_id` (required): UUID of the account

**Query Parameters:**
- `start_date` (optional): ISO 8601 date string
- `end_date` (optional): ISO 8601 date string
- `limit` (optional): Number of transactions (default: 50, max: 500)
- `offset` (optional): Pagination offset
- `category` (optional): Filter by category name

**Response:**
```json
{
  "transactions": [
    {
      "id": "uuid",
      "amount": -45.67,
      "description": "AMAZON.COM PURCHASE",
      "date": "2026-01-20T14:22:00Z",
      "category_name": "Shopping",
      "is_income": false,
      "merchant": "Amazon"
    }
  ],
  "pagination": {
    "total": 150,
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

### POST /accounts/link
Initiate account linking process (integrates with Plaid or similar service).

**Request:**
```json
{
  "institution_id": "ins_3",
  "public_token": "public-sandbox-xxxx-xxxx"
}
```

**Response:**
```json
{
  "account": {
    "id": "uuid",
    "institution_name": "Chase",
    "account_name": "Total Checking",
    "account_type": "checking",
    "balance": 4523.67,
    "last_updated": "2026-01-21T10:30:00Z",
    "is_linked": true,
    "account_number_last4": "4521"
  },
  "link_status": "success"
}
```

### DELETE /accounts/{account_id}
Unlink a bank account.

**Path Parameters:**
- `account_id` (required): UUID of the account

**Response:**
```json
{
  "success": true,
  "message": "Account unlinked successfully"
}
```

### POST /accounts/{account_id}/refresh
Refresh account balance and transactions.

**Path Parameters:**
- `account_id` (required): UUID of the account

**Response:**
```json
{
  "balance": 4678.90,
  "last_updated": "2026-01-21T11:00:00Z"
}
```

---

## AI Chat APIs

### POST /chat/message
Send a message to the AI financial advisor.

**Request:**
```json
{
  "message": "How can I save more money each month?",
  "context": [
    {
      "id": "uuid",
      "content": "Previous user message",
      "is_from_user": true,
      "timestamp": "2026-01-21T10:00:00Z"
    },
    {
      "id": "uuid",
      "content": "Previous AI response",
      "is_from_user": false,
      "timestamp": "2026-01-21T10:00:05Z"
    }
  ],
  "include_financial_context": true
}
```

**Response:**
```json
{
  "response": {
    "id": "uuid",
    "content": "Great question about savings! Based on your spending patterns, I'd recommend the 50/30/20 rule...",
    "timestamp": "2026-01-21T10:35:00Z",
    "message_type": "text",
    "suggestions": [
      "Set a savings goal",
      "Review my spending",
      "Create a budget"
    ]
  }
}
```

### POST /chat/generate-plan
Generate a personalized financial plan based on chat context.

**Request:**
```json
{
  "context": [
    {
      "id": "uuid",
      "content": "I want to save for a vacation",
      "is_from_user": true,
      "timestamp": "2026-01-21T10:00:00Z"
    }
  ],
  "include_transactions": true,
  "time_horizon_months": 12
}
```

**Response:**
```json
{
  "plan": {
    "id": "uuid",
    "summary": "Based on our conversation, here's your personalized financial plan!",
    "recommendations": [
      "Build a 3-month emergency fund of $6,000",
      "Reduce dining out expenses by 25%",
      "Set up automatic transfers of $500/month to savings"
    ],
    "monthly_target_savings": 500,
    "generated_at": "2026-01-21T10:36:00Z",
    "is_active": true,
    "suggested_goals": [
      {
        "title": "Emergency Fund",
        "target_amount": 6000,
        "target_date": "2026-07-01",
        "category": "emergency",
        "priority": 1
      }
    ]
  }
}
```

### POST /chat/suggest-goals
Get AI-suggested goals based on transaction history.

**Request:**
```json
{
  "date_range": {
    "start": "2025-07-01",
    "end": "2026-01-21"
  }
}
```

**Response:**
```json
{
  "suggested_goals": [
    {
      "title": "Emergency Fund",
      "description": "Build a 3-month safety net",
      "target_amount": 6000,
      "suggested_target_date": "2026-07-01",
      "category": "emergency",
      "reasoning": "Based on your monthly expenses, a 3-month emergency fund would be $6,000"
    }
  ]
}
```

---

## Analytics APIs

### GET /analytics/cash-flow
Get cash flow data for visualizations.

**Query Parameters:**
- `start_date` (required): ISO 8601 date string
- `end_date` (required): ISO 8601 date string
- `granularity` (optional): "daily" | "weekly" | "monthly" (default: "daily")

**Response:**
```json
{
  "inflows": [
    {
      "date": "2026-01-01",
      "amount": 3500.00
    }
  ],
  "outflows": [
    {
      "date": "2026-01-01",
      "amount": 150.00
    }
  ],
  "net_flow": 2300.00,
  "total_inflow": 7000.00,
  "total_outflow": 4700.00
}
```

### GET /analytics/spending-by-category
Get spending breakdown by category.

**Query Parameters:**
- `start_date` (required): ISO 8601 date string
- `end_date` (required): ISO 8601 date string

**Response:**
```json
{
  "categories": [
    {
      "category_name": "Food & Dining",
      "icon_name": "fork.knife",
      "color_hex": "#FF6B6B",
      "amount": 485.50,
      "percentage": 0.27,
      "transaction_count": 23
    }
  ],
  "total_spending": 1800.00
}
```

### GET /analytics/budget-comparison
Get budget vs actual spending comparison.

**Query Parameters:**
- `month` (required): "YYYY-MM" format string

**Response:**
```json
{
  "budgeted": 2000.00,
  "actual": 1850.00,
  "is_over_budget": false,
  "percent_used": 0.925,
  "by_category": [
    {
      "category_name": "Food & Dining",
      "budgeted": 500.00,
      "actual": 485.50,
      "is_over_budget": false
    }
  ]
}
```

### GET /analytics/savings-progress
Get progress on all savings goals.

**Response:**
```json
{
  "goals": [
    {
      "goal": {
        "id": "uuid",
        "title": "Emergency Fund",
        "target_amount": 6000,
        "current_amount": 2400,
        "target_date": "2026-07-01",
        "progress": 0.4
      },
      "monthly_contribution": 400,
      "projected_completion_date": "2026-08-15",
      "on_track": true
    }
  ],
  "total_saved": 3700,
  "total_target": 14000,
  "overall_progress": 0.264
}
```

---

## Goals APIs

### GET /goals
Fetch all financial goals.

**Query Parameters:**
- `status` (optional): "active" | "completed" | "all" (default: "active")
- `category` (optional): Filter by goal category

**Response:**
```json
{
  "goals": [
    {
      "id": "uuid",
      "title": "Emergency Fund",
      "description": "Build a 3-month safety net",
      "target_amount": 6000.00,
      "current_amount": 2400.00,
      "target_date": "2026-07-01",
      "created_at": "2026-01-01T00:00:00Z",
      "category": "emergency",
      "is_ai_generated": true,
      "priority": 1,
      "progress": 0.4
    }
  ]
}
```

### POST /goals
Create a new financial goal.

**Request:**
```json
{
  "title": "Vacation Fund",
  "description": "Trip to Japan",
  "target_amount": 5000,
  "current_amount": 500,
  "target_date": "2027-01-01",
  "category": "vacation"
}
```

**Response:**
```json
{
  "goal": {
    "id": "uuid",
    "title": "Vacation Fund",
    "description": "Trip to Japan",
    "target_amount": 5000,
    "current_amount": 500,
    "target_date": "2027-01-01",
    "created_at": "2026-01-21T10:00:00Z",
    "category": "vacation",
    "is_ai_generated": false,
    "priority": 0,
    "progress": 0.1
  }
}
```

### PUT /goals/{goal_id}
Update an existing goal.

**Path Parameters:**
- `goal_id` (required): UUID of the goal

**Request:**
```json
{
  "title": "Vacation Fund - Japan 2027",
  "current_amount": 750
}
```

**Response:**
```json
{
  "goal": {
    "id": "uuid",
    "title": "Vacation Fund - Japan 2027",
    "current_amount": 750,
    "progress": 0.15
  }
}
```

### DELETE /goals/{goal_id}
Delete a goal.

**Path Parameters:**
- `goal_id` (required): UUID of the goal

**Response:**
```json
{
  "success": true,
  "message": "Goal deleted successfully"
}
```

### POST /goals/{goal_id}/contribute
Add a contribution to a goal.

**Path Parameters:**
- `goal_id` (required): UUID of the goal

**Request:**
```json
{
  "amount": 100.00,
  "note": "Weekly savings contribution"
}
```

**Response:**
```json
{
  "goal": {
    "id": "uuid",
    "current_amount": 850.00,
    "progress": 0.17
  },
  "contribution": {
    "id": "uuid",
    "amount": 100.00,
    "date": "2026-01-21T10:00:00Z",
    "note": "Weekly savings contribution"
  }
}
```

---

## Financial Plan APIs

### GET /plans
Get all financial plans (usually just the active one).

**Query Parameters:**
- `active_only` (optional): boolean (default: true)

**Response:**
```json
{
  "plans": [
    {
      "id": "uuid",
      "summary": "Your personalized financial plan...",
      "recommendations": [
        "Build a 3-month emergency fund",
        "Reduce dining expenses by 20%"
      ],
      "monthly_target_savings": 500,
      "generated_at": "2026-01-15T10:00:00Z",
      "is_active": true
    }
  ]
}
```

### POST /plans
Create a new financial plan (typically from AI chat).

**Request:**
```json
{
  "summary": "Based on your financial profile...",
  "recommendations": [
    "Build emergency fund",
    "Reduce spending"
  ],
  "monthly_target_savings": 500,
  "goal_ids": ["uuid1", "uuid2"]
}
```

### PUT /plans/{plan_id}/deactivate
Deactivate a plan.

**Response:**
```json
{
  "success": true,
  "message": "Plan deactivated"
}
```

---

## Error Responses

All endpoints may return error responses in this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional context if applicable"
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or expired authentication token |
| `FORBIDDEN` | 403 | User doesn't have permission |
| `NOT_FOUND` | 404 | Requested resource not found |
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | External service (bank API) unavailable |

---

## Rate Limiting

API requests are rate limited per user:

- **Standard endpoints**: 100 requests per minute
- **AI Chat endpoints**: 20 requests per minute
- **Analytics endpoints**: 50 requests per minute

Rate limit headers are included in all responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642781234
```

---

## Webhooks (Future)

For real-time updates, the API supports webhooks for:

- `account.balance_updated` - When account balance changes
- `transaction.new` - New transaction detected
- `goal.completed` - Goal target reached
- `plan.generated` - New AI plan generated

---

## Data Types

### Account Types
- `checking`
- `savings`
- `credit`
- `investment`

### Goal Categories
- `savings`
- `debt_payoff`
- `emergency`
- `investment`
- `purchase`
- `retirement`
- `vacation`
- `custom`

### Message Types
- `text`
- `goal_suggestion`
- `budget_advice`
- `celebration`
- `question`
- `plan_generated`

---

## Implementation Notes

### Mock Service Layer

The current implementation uses mock services that simulate API behavior:

- `MockBankingService`: Simulates bank account and transaction APIs
- `MockAIService`: Provides canned AI responses for chat functionality
- `MockAnalyticsService`: Generates sample analytics data

### Transitioning to Real APIs

1. Create production implementations of each service protocol
2. Replace mock services in `ServiceContainer`
3. Add proper error handling and retry logic
4. Implement token refresh and authentication flow
5. Add offline caching with Core Data/SwiftData sync

### Security Considerations

- All API calls should use HTTPS
- Sensitive data (tokens, account numbers) should use Keychain
- Implement certificate pinning for production
- Never log sensitive financial data
- Use Plaid or similar service for bank linking (never handle credentials directly)
