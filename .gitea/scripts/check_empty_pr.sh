#!/bin/bash
# Check if a PR is empty (no changes compared to target branch)
# This script should be run in CI for pull requests.
# If the PR has no changes, it will exit with code 1 and print an error.

set -euo pipefail

# Get the target branch (default: main)
TARGET_BRANCH="origin/main"

# Check if we are in a CI environment (optional)
if [ -z "${CI:-}" ]; then
    echo "Not running in CI, skipping empty PR check."
    exit 0
fi

# If current branch is main, this is not a PR, skip the check
current_branch="${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD)}"
if [ "$current_branch" = "main" ]; then
    echo "Current branch is main, not a PR. Skipping empty PR check."
    exit 0
fi

# Get the list of changed files between current HEAD and target branch
changed_files=$(git diff --name-only "$TARGET_BRANCH" HEAD 2>/dev/null || true)

if [ -z "$changed_files" ]; then
    echo "ERROR: This PR appears to be empty (no changes compared to $TARGET_BRANCH)."
    echo "Please make sure your PR contains actual changes."
    exit 1
else
    echo "PR contains changes. Changed files:"
    echo "$changed_files"
    echo "Total changed files: $(echo "$changed_files" | wc -l)"
fi
