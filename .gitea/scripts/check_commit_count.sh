#!/bin/bash

# This script checks if the number of commits in a PR is reasonable.
# It fails if:
#   - number of commits > number of files changed

set -e

echo "Checking if commit count is reasonable..."

# Check if we're in a PR context
if ! git rev-parse --verify origin/main >/dev/null 2>&1; then
    echo "WARNING: Cannot find origin/main reference, skipping commit count check"
    exit 0
fi

# Get the number of commits in the PR (from origin/main to HEAD)
commit_count=$(git log --oneline origin/main..HEAD | wc -l)

# Get the number of files changed (excluding deleted files)
file_count=$(git diff --name-only --diff-filter=ACMR origin/main..HEAD | wc -l)

echo "Number of commits: $commit_count"
echo "Number of files changed: $file_count"

# If commit count exceeds file count, fail
if [ "$commit_count" -gt "$file_count" ]; then
    echo "ERROR: PR has $commit_count commits but only $file_count files changed."
    echo "       Please squash commits to have at most one commit per file changed."
    exit 1
else
    echo "SUCCESS: Commit count check passed."
    exit 0
fi
