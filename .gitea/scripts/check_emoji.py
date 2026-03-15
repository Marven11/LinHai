import sys
import subprocess
import re


def get_commit_messages(base_ref="origin/main"):
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
        cmd = ["git", "log", f"{base_ref}..HEAD", "--oneline"]
        output = subprocess.check_output(
            cmd, universal_newlines=True, stderr=subprocess.DEVNULL
        )
        return output.strip().split("\n")
    except subprocess.CalledProcessError:
        return []


def contains_emoji(text):
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "]",
        flags=re.UNICODE,
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
