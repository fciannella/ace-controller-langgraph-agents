#!/bin/bash

# Default to .env if no file is specified
ENV_FILE="${1:-.env}"

# Check if file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ Error: $ENV_FILE does not exist."
  exit 1
fi

# Export all non-commented, non-empty lines
export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)

echo "✅ Environment variables loaded from $ENV_FILE"
