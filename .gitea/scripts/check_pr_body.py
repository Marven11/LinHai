import json
import os
import sys


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not os.path.exists(event_path):
        print("Not in CI or event path not found, skipping check.")
        sys.exit(0)

    with open(event_path) as f:
        event = json.load(f)

    pr = event.get("pull_request", {})
    body = pr.get("body", "") or ""

    non_empty_lines = [line for line in body.splitlines() if line.strip()]

    if len(non_empty_lines) < 3:
        print("ERROR: 当前PR介绍几乎为空，请详细介绍PR完成的内容，对各个部分做出的修改")
        sys.exit(1)

    print(f"PR body has {len(non_empty_lines)} non-empty lines. Check passed.")


if __name__ == "__main__":
    main()
