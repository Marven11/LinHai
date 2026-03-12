import sys
import os
import subprocess

try:
    import tokenize
except ImportError:
    print("ERROR: Failed to import tokenize module")
    sys.exit(1)


def is_docstring(token_type, token_string):
    """
    Check if a token is a docstring (triple-quoted string).
    """
    stripped = token_string.strip()
    return token_type == tokenize.STRING and (
        stripped.startswith('"""') or stripped.startswith("'''")
    )


def get_comment_lines_in_diff(file_path, base_ref="origin/main"):
    """
    Get line numbers of newly added comments in the diff for a given file.
    Returns a set of line numbers.
    """
    comment_lines = set()
    try:
        # Check if base_ref exists, fallback to HEAD^
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        subprocess.run(check_cmd, capture_output=True, check=False)
        # If not exists, use HEAD^
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
        cmd = ["git", "diff", "--unified=0", base_ref, "HEAD", "--", file_path]
        diff_output = subprocess.check_output(
            cmd, universal_newlines=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return comment_lines

    lines = diff_output.split("\n")
    current_line_number = None
    for line in lines:
        if line.startswith("@@"):
            parts = line.split(" ")
            for part in parts:
                if part.startswith("+"):
                    try:
                        current_line_number = int(part[1:].split(",")[0])
                    except ValueError:
                        pass
                    break
        elif line.startswith("+") and not line.startswith("+++"):
            if current_line_number is not None:
                if "#" in line and not line.strip().startswith("#"):
                    comment_lines.add(current_line_number)
                current_line_number += 1
    return comment_lines


def check_file_for_new_comments(file_path, base_ref="origin/main"):
    """
    Check a Python file for newly added comments in the diff.
    Returns True if new comments found, False otherwise.
    """
    comment_lines_in_diff = get_comment_lines_in_diff(file_path, base_ref)
    if not comment_lines_in_diff:
        return False

    try:
        with open(file_path, "rb") as f:
            tokens = list(tokenize.tokenize(f.readline))
    except Exception as e:
        print(f"ERROR: Failed to tokenize {file_path}: {e}")
        return False

    for token in tokens:
        if token.type == tokenize.COMMENT:
            token_line = token.start[0]
            if token_line in comment_lines_in_diff:
                print(
                    f"ERROR: New comment added at {file_path}:{token_line}: {token.string.strip()}"
                )
                return True
    return False


def main():
    """
    Main function to check all Python files in linhai/ directory for new comments.
    """
    base_ref = "origin/main"
    try:
        # Check if origin/main exists, fallback to HEAD^
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
    except Exception:
        base_ref = "HEAD^"
    try:
        cmd = ["git", "diff", "--name-only", base_ref, "HEAD", "--", "linhai/"]
        print(f"DEBUG: Running git diff command: {' '.join(cmd)}")
        changed_files = (
            subprocess.check_output(
                cmd, universal_newlines=True, stderr=subprocess.DEVNULL
            )
            .strip()
            .split("\n")
        )
        print(f"DEBUG: Changed files: {changed_files}")
    except subprocess.CalledProcessError as e:
        print(f"DEBUG: Git diff failed: {e}")
        changed_files = []

    python_files = [f for f in changed_files if f.endswith(".py") and os.path.exists(f)]
    print(f"DEBUG: Python files to check: {python_files}")

    if not python_files:
        print("No Python files changed in linhai/ directory.")
        sys.exit(0)

    errors_found = False
    for file_path in python_files:
        if check_file_for_new_comments(file_path, base_ref):
            errors_found = True

    if errors_found:
        print(
            "\nERROR: New comments detected. Please remove them or convert to docstrings."
        )
        sys.exit(1)
    else:
        print("SUCCESS: No new comments found in changed Python files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
