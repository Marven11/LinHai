import sys
import os
import subprocess
import re


def get_changed_files(base_ref="origin/main"):
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
        cmd = ["git", "diff", "--name-only", f"{base_ref}..HEAD"]
        output = subprocess.check_output(
            cmd, universal_newlines=True, stderr=subprocess.DEVNULL
        )
        return output.strip().split("\n")
    except subprocess.CalledProcessError:
        return []


def is_snapshot_document(filepath):
    if not filepath.endswith(".md"):
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False

    if len(lines) < 100:
        return False

    # 检查大部分行是否以空格和'-'开头
    dash_line_count = 0
    ref_line_count = 0

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("-"):
            dash_line_count += 1
        if "ref=" in line:
            ref_line_count += 1

    dash_ratio = dash_line_count / len(lines)
    ref_ratio = ref_line_count / len(lines)

    # 特征：大部分行以'-'开头（例如80%），且至少30%行包含'ref='
    return dash_ratio > 0.8 and ref_ratio > 0.3


def main():
    base_ref = "origin/main"
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
    except Exception:
        base_ref = "HEAD^"

    changed_files = get_changed_files(base_ref)
    if not changed_files:
        print("No files changed.")
        sys.exit(0)

    errors = []
    for filepath in changed_files:
        if not filepath:
            continue
        if os.path.exists(filepath) and is_snapshot_document(filepath):
            errors.append(filepath)

    if errors:
        print("ERROR: Potential browser MCP snapshot documents detected:")
        for err in errors:
            print(f"  {err}")
        print(
            "\nThese appear to be browser MCP snapshot outputs, not proper documentation."
        )
        print(
            "Please remove these files or ensure they are not accidentally committed."
        )
        sys.exit(1)
    else:
        print("SUCCESS: No suspicious snapshot documents found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
