#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Deploying Supabase migrations..."
cd "$ROOT_DIR/supabase"
supabase db push

echo "Deploying edge functions..."
supabase functions deploy verify-api-key
supabase functions deploy apns-router

echo "Setting secrets..."
supabase secrets set --env-file "$ROOT_DIR/.env"

echo "Supabase deploy complete."
