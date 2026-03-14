#!/bin/bash

# This script checks for garbage code patterns in new lines added to Python files
# in the linhai/ directory. It looks for:
# 1. hasattr/getattr/setattr function calls
# 2. try: except: patterns

set -e

echo "Checking for garbage code patterns in new lines..."

# Get list of changed Python files in linhai/ directory
if ! git diff --name-only origin/main HEAD -- linhai/ | grep -E '\.py$' > /tmp/changed_py_files.txt; then
    echo "No Python files changed in linhai/ directory."
    exit 0
fi

errors_found=false

# Read each changed file
while IFS= read -r file_path; do
    if [ ! -f "$file_path" ]; then
        continue
    fi
    
    echo "Checking $file_path..."
    
    # Get unified diff for this file
    git diff --unified=0 origin/main HEAD -- "$file_path" | grep '^+' | grep -v '^+++' > /tmp/diff_lines.txt || true
    
    # Check each added line for garbage patterns
    line_num=1
    while IFS= read -r line; do
        # Skip empty lines and lines that are just "+"
        if [ -z "${line:1}" ]; then
            continue
        fi
        
        # Check for hasattr/getattr/setattr
        if echo "$line" | grep -q -E '\bhasattr\b|\bgetattr\b|\bsetattr\b'; then
            echo "ERROR: Found hasattr/getattr/setattr in new line at $file_path (line in diff): $line"
            errors_found=true
        fi
        
        # Check for try: except: patterns (only new additions)
        if echo "$line" | grep -q -E '^\+?\s*try:\s*$|^\+?\s*except\s+\(?[^)]*\)?\s*:|^\+?\s*except\s*:\s*$'; then
            echo "ERROR: Found try/except pattern in new line at $file_path (line in diff): $line"
            errors_found=true
        fi

        # Check for import
        if echo "$line" | grep -q -E '^\s+?\s+import [a-z]+$'; then
            echo "ERROR: Found bad import pattern: $line"
            errors_found=true
        fi

        line_num=$((line_num + 1))
    done < /tmp/diff_lines.txt
    
    rm -f /tmp/diff_lines.txt

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