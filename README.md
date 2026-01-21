# Saverr API Infrastructure

Serverless backend infrastructure for the Saverr personal finance app, built with AWS SAM (Serverless Application Model).

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                    │
│                                                                          │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐    │
│  │   API Gateway   │────▶│  Lambda Layer   │────▶│    DynamoDB     │    │
│  │   (HTTP API)    │     │   (Functions)   │     │    (Tables)     │    │
│  └────────┬────────┘     └────────┬────────┘     └─────────────────┘    │
│           │                       │                                      │
│           │                       │              ┌─────────────────┐    │
│  ┌────────▼────────┐              │              │ Secrets Manager │    │
│  │    Cognito      │              └─────────────▶│  (Plaid Keys)   │    │
│  │   User Pool     │                             └─────────────────┘    │
│  │ (JWT Auth)      │                                                     │
│  └─────────────────┘              ┌─────────────────┐                   │
│                                   │ Amazon Bedrock  │                   │
│                                   │   (AI Chat)     │                   │
│                                   └─────────────────┘                   │
└──────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Authentication**: AWS Cognito with JWT tokens
- **API Gateway**: HTTP API with Cognito authorizer
- **Lambda Functions**: Python 3.11 serverless functions
- **Database**: DynamoDB with single-table design
- **AI Features**: Amazon Bedrock (Claude) for chat and recommendations
- **Bank Integration**: Plaid API for account linking
- **Security**: Encrypted at rest, IAM least-privilege, secret management

## Project Structure

```
SaverrInfra/
├── template.yaml              # CloudFormation/SAM template
├── samconfig.toml             # SAM deployment configuration
├── deploy.sh                  # Deployment script
├── lambdas/
│   ├── auth/                  # Authentication endpoints
│   │   ├── login.py
│   │   ├── signup.py
│   │   ├── confirm.py
│   │   ├── resend_code.py
│   │   ├── refresh.py
│   │   ├── forgot_password.py
│   │   └── reset_password.py
│   ├── accounts/              # Bank account endpoints
│   │   ├── list_accounts.py
│   │   ├── get_account.py
│   │   ├── link_account.py
│   │   ├── delete_account.py
│   │   ├── refresh_account.py
│   │   └── get_transactions.py
│   ├── goals/                 # Financial goals endpoints
│   │   ├── list_goals.py
│   │   ├── create_goal.py
│   │   ├── get_goal.py
│   │   ├── update_goal.py
│   │   ├── delete_goal.py
│   │   └── contribute_to_goal.py
│   ├── plans/                 # Financial plans endpoints
│   │   ├── list_plans.py
│   │   ├── create_plan.py
│   │   └── deactivate_plan.py
│   ├── chat/                  # AI chat endpoints
│   │   ├── send_message.py
│   │   ├── generate_plan.py
│   │   └── suggest_goals.py
│   ├── analytics/             # Analytics endpoints
│   │   ├── get_cash_flow.py
│   │   ├── get_spending_by_category.py
│   │   ├── get_budget_comparison.py
│   │   └── get_savings_progress.py
│   └── shared/                # Shared utilities
│       ├── auth.py
│       ├── database.py
│       ├── response.py
│       └── validation.py
└── API_DOCUMENTATION.md       # Full API documentation
```

## API Endpoints

### Authentication (No auth required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | Register new user |
| POST | `/auth/confirm` | Confirm email |
| POST | `/auth/login` | Login and get tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/forgot-password` | Request password reset |
| POST | `/auth/reset-password` | Complete password reset |

### Accounts (Auth required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/accounts` | List all accounts |
| GET | `/accounts/{id}` | Get account details |
| POST | `/accounts/link` | Link new bank account |
| DELETE | `/accounts/{id}` | Unlink account |
| POST | `/accounts/{id}/refresh` | Refresh account data |
| GET | `/accounts/{id}/transactions` | Get transactions |

### Goals (Auth required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/goals` | List all goals |
| POST | `/goals` | Create new goal |
| GET | `/goals/{id}` | Get goal details |
| PUT | `/goals/{id}` | Update goal |
| DELETE | `/goals/{id}` | Delete goal |
| POST | `/goals/{id}/contribute` | Add contribution |

### Plans (Auth required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/plans` | List financial plans |
| POST | `/plans` | Create new plan |
| PUT | `/plans/{id}/deactivate` | Deactivate plan |

### Chat (Auth required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/message` | Send message to AI |
| POST | `/chat/generate-plan` | Generate financial plan |
| POST | `/chat/suggest-goals` | Get AI goal suggestions |

### Analytics (Auth required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/cash-flow` | Cash flow data |
| GET | `/analytics/spending-by-category` | Spending breakdown |
| GET | `/analytics/budget-comparison` | Budget vs actual |
| GET | `/analytics/savings-progress` | Goal progress |

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **SAM CLI** installed (`brew install aws-sam-cli`)
3. **Docker** for local testing and builds
4. **Python 3.11+** for local development

## Deployment

### First-time Setup

```bash
# Clone the repository
cd SaverrInfra

# Deploy to dev environment
./deploy.sh dev
```

### Deploy to Different Environments

```bash
# Development
./deploy.sh dev

# Staging
./deploy.sh staging

# Production (requires confirmation)
./deploy.sh prod
```

### Manual SAM Commands

```bash
# Build
sam build --use-container

# Deploy with guided prompts
sam deploy --guided

# Deploy to specific environment
sam deploy --config-env prod
```

## Post-Deployment Configuration

### 1. Update Plaid Credentials

After deployment, update the Plaid secret in AWS Secrets Manager:

```bash
aws secretsmanager update-secret \
  --secret-id saverr/plaid/dev \
  --secret-string '{
    "client_id": "YOUR_PLAID_CLIENT_ID",
    "secret": "YOUR_PLAID_SECRET",
    "environment": "sandbox"
  }'
```

### 2. Configure iOS App

Update your iOS app with the deployment outputs:

```swift
// Config.swift
struct APIConfig {
    static let baseURL = "https://xxxxx.execute-api.us-east-1.amazonaws.com/dev"
    static let cognitoUserPoolId = "us-east-1_XXXXXXXX"
    static let cognitoClientId = "xxxxxxxxxxxxxxxxxxxxxxxxxx"
    static let region = "us-east-1"
}
```

## Local Development

### Run API Locally

```bash
# Start local API
sam local start-api

# Invoke a specific function
sam local invoke LoginFunction --event events/login.json
```

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-cov moto

# Run tests
pytest tests/ -v --cov=lambdas
```

## Security Features

- **Authentication**: AWS Cognito with JWT tokens
- **Authorization**: API Gateway Cognito Authorizer
- **Encryption at Rest**: DynamoDB SSE, Secrets Manager encryption
- **Encryption in Transit**: HTTPS only via API Gateway
- **IAM Least Privilege**: Lambda roles with minimal permissions
- **Password Policy**: Minimum 8 characters with complexity requirements
- **MFA Support**: Optional TOTP MFA via Cognito
- **Advanced Security**: Cognito Advanced Security (ENFORCED in prod)

## Monitoring & Observability

- **AWS X-Ray**: Distributed tracing enabled on all functions
- **CloudWatch Logs**: Automatic log collection
- **CloudWatch Alarms**: 5xx errors and Lambda errors (prod only)
- **CloudWatch Metrics**: API Gateway and Lambda metrics

## Cost Optimization

- **Pay-per-request**: DynamoDB and Lambda pricing
- **No idle costs**: Serverless architecture
- **Efficient code**: Optimized for cold start and execution time

## Contributing

1. Create a feature branch
2. Make changes and test locally
3. Run `sam validate` to validate template
4. Submit a pull request

## License

Proprietary - All rights reserved
