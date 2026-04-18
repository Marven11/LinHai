#!/bin/bash

set -e

echo "Checking for garbage code patterns in new lines..."

if ! git diff -M --name-only origin/main HEAD -- linhai/ | grep -E '\.py$' > /tmp/changed_py_files.txt; then
    echo "No Python files changed in linhai/ directory."
    exit 0
fi

errors_found=false

full_diff=$(git diff -M --unified=0 origin/main HEAD -- linhai/)

while IFS= read -r file_path; do
    if [ ! -f "$file_path" ]; then
        continue
    fi

    file_diff=$(echo "$full_diff" | awk -v fp="b/$file_path" '
        /^diff --git / { found=0 }
        /^diff --git / && $0 ~ fp"$" { found=1 }
        found && /^\+/ && !/^\+\+\+/ { print }
    ')

    if [ -z "$file_diff" ]; then
        continue
    fi

    echo "Checking $file_path..."

    while IFS= read -r line; do
        content="${line:1}"
        if [ -z "$content" ]; then
            continue
        fi

        if echo "$content" | grep -q -E '\bhasattr\b|\bgetattr\b|\bsetattr\b'; then
            echo "ERROR: Found hasattr/getattr/setattr in new line at $file_path: $content"
            errors_found=true
        fi

        if echo "$content" | grep -q -E '^\s*try:\s*$|^\s*except\s+\(?[^)]*\)?\s*:|^\s*except\s*:\s*$'; then
            echo "ERROR: Found try/except pattern in new line at $file_path: $content"
            errors_found=true
        fi

        if echo "$content" | grep -q -E '^\s+import [a-z]+$'; then
            echo "ERROR: Found bad import pattern: $content"
            errors_found=true
        fi
    done <<< "$file_diff"

done < /tmp/changed_py_files.txt

rm -f /tmp/changed_py_files.txt

if [ "$errors_found" = true ]; then
    echo "\nERROR: Garbage code patterns detected in new lines."
    echo "Please remove hasattr/getattr/setattr calls, try/except and bad import patterns from new code."
    exit 1
else
    echo "SUCCESS: No garbage code patterns found in new lines."
    exit 0
fi