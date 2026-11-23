#!/usr/bin/env bash
set -euo pipefail

# Run in an authenticated GitHub CLI environment. Creates a NEW public repo.
# Never stores credentials in this project or asks for a token in source code.
cd "$(dirname "$0")/.."
command -v gh >/dev/null || { echo "Install the official GitHub CLI first: https://cli.github.com" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Run gh auth login, then run this script again." >&2; exit 1; }
if git remote get-url origin >/dev/null 2>&1; then
  echo "An origin already exists. Inspect it before publishing; no remote was changed." >&2
  exit 1
fi
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  git init -b main
  git add .
  git commit -m "Build QubitYield decision workbench and reproducible evidence"
fi
gh repo create qubit-yield --public --source . --remote origin --push \
  --description "Quantum hardware decisions grounded in reproducible circuit experiments and customer economics."

