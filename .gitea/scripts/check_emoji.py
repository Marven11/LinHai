import sys
import subprocess
import re

def get_commit_messages(base_ref="origin/main"):
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
        cmd = ["git", "log", f"{base_ref}..HEAD", "--oneline"]
        output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.DEVNULL)
        return output.strip().split("\n")
    except subprocess.CalledProcessError:
        return []

def contains_emoji(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "]",
        flags=re.UNICODE
    )
    return bool(emoji_pattern.search(text))

def main():
    base_ref = "origin/main"
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
    except Exception:
        base_ref = "HEAD^"

    commits = get_commit_messages(base_ref)
    if not commits:
        print("No new commits found.")
        sys.exit(0)

    errors = []
    for commit in commits:
        if contains_emoji(commit):
            errors.append(commit)

    if errors:
        print("ERROR: Emoji detected in commit messages:")
        for err in errors:
            print(f"  {err}")
        print("\nPlease remove emoji from commit messages.")
        sys.exit(1)
    else:
        print("SUCCESS: No emoji found in new commit messages.")
        sys.exit(0)

if __name__ == "__main__":
    main()