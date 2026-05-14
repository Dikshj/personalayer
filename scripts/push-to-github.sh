#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

echo "Reviewing changes..."
git diff --stat

echo ""
read -p "Commit message: " msg
read -p "Branch to push (default: main): " branch
branch=${branch:-main}

git add -A
git commit -m "$msg"
git push origin "$branch"

echo "Pushed to GitHub: $(git remote get-url origin)"
