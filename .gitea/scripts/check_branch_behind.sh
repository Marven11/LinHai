#!/bin/bash
set -euo pipefail

if [ -z "${CI:-}" ]; then
    echo "Not running in CI, skipping branch behind check."
    exit 0
fi

if git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
    echo "Branch is up to date with main."
else
    echo "ERROR: Branch is behind or diverged from main."
    echo "Please rebase your branch onto main: git fetch upstream && git rebase upstream/main"
    exit 1
fi
