import json
import sys
import urllib.request
import urllib.error
import os


def api_get(url, token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {token}")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not os.path.exists(event_path):
        print("Not in CI or event path not found, skipping check.")
        sys.exit(0)

    with open(event_path) as f:
        event = json.load(f)

    pr = event.get("pull_request", {})
    pr_number = pr.get("number", 0)

    server_url = os.environ.get("GITHUB_SERVER_URL", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")

    if not server_url or not repo or not token:
        print("WARNING: Missing server info, skipping check.")
        sys.exit(0)

    owner, repo_name = repo.split("/")
    api_base = f"{server_url}/api/v1/repos/{owner}/{repo_name}"

    issues = api_get(f"{api_base}/issues?state=open&type=issues", token)
    linked_issues = []
    for issue in issues:
        timeline = api_get(f"{api_base}/issues/{issue['number']}/timeline", token)
        for entry in timeline:
            if entry.get("type") != "pull_ref":
                continue
            if entry.get("ref_action") != "closes":
                continue
            ref_pr = entry.get("ref_issue", {})
            if ref_pr.get("number") == pr_number:
                linked_issues.append(issue["number"])
                break

    if not linked_issues:
        print(f"ERROR: PR #{pr_number} does not reference any issue to close.")
        print("Please add 'resolve #<issue>' or 'fix #<issue>' to the PR description.")
        sys.exit(1)

    print(f"PR #{pr_number} will close issues: {linked_issues}")

    has_error = False
    for issue_num in linked_issues:
        timeline = api_get(f"{api_base}/issues/{issue_num}/timeline", token)
        competing = []
        for entry in timeline:
            if entry.get("type") != "pull_ref":
                continue
            if entry.get("ref_action") != "closes":
                continue
            ref_pr = entry.get("ref_issue", {})
            if ref_pr.get("number") == pr_number:
                continue
            pr_state = ref_pr.get("state", "closed")
            if pr_state == "open":
                competing.append(ref_pr["number"])

        if competing:
            print(
                f"ERROR: Issue #{issue_num} is also targeted by open PR(s): {competing}"
            )
            has_error = True
        else:
            print(f"OK: Issue #{issue_num} is uniquely targeted by this PR.")

    if has_error:
        print("Please resolve the conflicting PRs before merging.")
        sys.exit(1)

    print("SUCCESS: PR issue check passed.")


if __name__ == "__main__":
    main()
