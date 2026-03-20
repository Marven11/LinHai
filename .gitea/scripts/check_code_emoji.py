import sys
import os
import re
import subprocess


def contains_emoji(text):
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300  \U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "]",
        flags=re.UNICODE,
    )
    return bool(emoji_pattern.search(text))


def get_changed_files():
    current_branch = os.environ.get("GITHUB_REF_NAME", "")
    target_branch = os.environ.get("GITHUB_BASE_REF", "main")
    if not current_branch:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
            )
            current_branch = result.stdout.strip()
        except:
            current_branch = "HEAD"
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{target_branch}...{current_branch}", "--"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Warning: git diff failed: {result.stderr}")
            return []
        files = result.stdout.strip().split("\n")
        python_files = [f for f in files if f and f.endswith(".py")]
        return python_files
    except Exception as e:
        print(f"Warning: Could not get changed files: {e}")
        return []


def check_changed_files():
    changed_files = get_changed_files()
    if not changed_files:
        print("No Python files changed in this PR.")
        return []
    errors = []
    for filepath in changed_files:
        if not os.path.exists(filepath):
            print(f"Warning: File {filepath} does not exist.")
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                if contains_emoji(content):
                    errors.append(filepath)
        except Exception as e:
            print(f"Warning: Could not read {filepath}: {e}")
    return errors


def main():
    print("Checking for emoji in changed Python files...")
    errors = check_changed_files()
    if errors:
        print("ERROR: Emoji detected in changed code files:")
        for err in errors:
            print(f"  {err}")
        print("\nPlease remove emoji from changed code files.")
        sys.exit(1)
    else:
        print("SUCCESS: No emoji found in changed code files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
