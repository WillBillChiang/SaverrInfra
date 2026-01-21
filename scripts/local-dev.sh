#!/bin/bash

# Saverr API - Local Development
# Usage: ./scripts/local-dev.sh [port]

set -e

PORT=${1:-3000}
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"

cd "$PROJECT_DIR"

echo "============================================"
echo "Saverr API - Local Development"
echo "============================================"
echo "Port: $PORT"
echo ""

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "Error: Docker is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

# Build first
echo "Building SAM application..."
sam build --config-env dev

echo ""
echo "Starting local API on http://localhost:$PORT"
echo "Press Ctrl+C to stop"
echo ""

# Start local API
sam local start-api \
    --port "$PORT" \
    --host 127.0.0.1 \
    --warm-containers EAGER \
    --env-vars environments/local-env.json 2>/dev/null || \
sam local start-api \
    --port "$PORT" \
    --host 127.0.0.1 \
    --warm-containers EAGER
