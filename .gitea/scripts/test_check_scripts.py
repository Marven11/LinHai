import json
import os
import sys
import subprocess
import tempfile
import shutil


def test_check_python_comments():
    """
    Test the check_python_comments.py script.
    """
    test_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    try:
        # Create linhai/ directory structure
        linhai_dir = os.path.join(test_dir, "linhai")
        os.makedirs(linhai_dir, exist_ok=True)

        # Step 1: Create a clean Python file without comments
        test_file = os.path.join(linhai_dir, "test_file.py")
        with open(test_file, "w") as f:
            f.write("def test_func():\n")
            f.write("    pass\n")

        # Initialize git
        os.chdir(test_dir)
        subprocess.run(["git", "init"], capture_output=True, check=False)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            capture_output=True,
            check=False,
        )
        subprocess.run(["git", "add", "."], capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "initial"], capture_output=True, check=False
        )
        # Create a tag to simulate origin/main
        subprocess.run(["git", "tag", "origin/main"], capture_output=True, check=False)

        # Step 2: Add a comment and commit
        with open(test_file, "w") as f:
            f.write("def test_func():\n")
            f.write("    pass  # This is a new comment\n")

        subprocess.run(["git", "add", "."], capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "add comment"], capture_output=True, check=False
        )

        # Run the check script - should fail because of the new comment
        script_path = os.path.join(
            original_dir, ".gitea/scripts/check_python_comments.py"
        )
        result = subprocess.run(
            [sys.executable, script_path], capture_output=True, text=True
        )

        if result.returncode != 1:
            print(
                "FAIL: check_python_comments.py should fail when new comment is added"
            )
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        # Step 3: Remove the comment and commit again
        with open(test_file, "w") as f:
            f.write("def test_func():\n")
            f.write("    pass\n")

        subprocess.run(["git", "add", "."], capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "remove comment"], capture_output=True, check=False
        )

        # Run the check script - should pass when no new comments
        result = subprocess.run(
            [sys.executable, script_path], capture_output=True, text=True
        )

        if result.returncode != 0:
            print("FAIL: check_python_comments.py should pass when no new comments")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        print("PASS: check_python_comments.py test")
        return True

    finally:
        os.chdir(original_dir)
        shutil.rmtree(test_dir)


def test_check_pr_body():
    """
    Test the check_pr_body.py script.
    """
    test_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    try:
        event_file = os.path.join(test_dir, "event.json")
        script_path = os.path.join(original_dir, ".gitea/scripts/check_pr_body.py")

        env = os.environ.copy()
        env.pop("GITHUB_EVENT_PATH", None)
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            print("FAIL: check_pr_body.py should skip without event file")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        with open(event_file, "w") as f:
            json.dump({"pull_request": {"body": "short desc\n"}}, f)
        env["GITHUB_EVENT_PATH"] = event_file
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 1:
            print("FAIL: check_pr_body.py should fail with < 3 lines")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        with open(event_file, "w") as f:
            json.dump(
                {"pull_request": {"body": "line 1\nline 2\nline 3\n"}},
                f,
            )
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            print("FAIL: check_pr_body.py should pass with 3+ lines")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        with open(event_file, "w") as f:
            json.dump({"pull_request": {"body": ""}}, f)
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 1:
            print("FAIL: check_pr_body.py should fail with empty body")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        with open(event_file, "w") as f:
            json.dump({"pull_request": {}}, f)
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 1:
            print("FAIL: check_pr_body.py should fail with None body")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        with open(event_file, "w") as f:
            json.dump(
                {"pull_request": {"body": "line 1\n   \nline 2\n"}},
                f,
            )
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 1:
            print("FAIL: check_pr_body.py should fail with whitespace-only lines")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        print("PASS: check_pr_body.py test")
        return True

    finally:
        os.chdir(original_dir)
        shutil.rmtree(test_dir)


def test_check_git_diff():
    """
    Test the check_git_diff.sh script.
    """
    test_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    try:
        # Create linhai/ directory structure
        linhai_dir = os.path.join(test_dir, "linhai")
        os.makedirs(linhai_dir, exist_ok=True)

        # Step 1: Create a clean Python file without hasattr
        test_file = os.path.join(linhai_dir, "test_file.py")
        with open(test_file, "w") as f:
            f.write("def test_func():\n")
            f.write("    obj = object()\n")
            f.write("    pass\n")

        # Initialize git
        os.chdir(test_dir)
        subprocess.run(["git", "init"], capture_output=True, check=False)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            capture_output=True,
            check=False,
        )
        subprocess.run(["git", "add", "."], capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "initial"], capture_output=True, check=False
        )
        # Create a tag to simulate origin/main
        subprocess.run(["git", "tag", "origin/main"], capture_output=True, check=False)

        # Step 2: Add hasattr and commit
        with open(test_file, "w") as f:
            f.write("def test_func():\n")
            f.write("    obj = object()\n")
            f.write("    if hasattr(obj, 'test'):\n")
            f.write("        pass\n")

        subprocess.run(["git", "add", "."], capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "add hasattr"], capture_output=True, check=False
        )

        # Run the check script - should fail because of hasattr
        script_path = os.path.join(original_dir, ".gitea/scripts/check_git_diff.sh")
        result = subprocess.run(["bash", script_path], capture_output=True, text=True)

        if result.returncode != 1:
            print("FAIL: check_git_diff.sh should fail when hasattr is added")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        # Step 3: Remove hasattr and commit again
        with open(test_file, "w") as f:
            f.write("def test_func():\n")
            f.write("    obj = object()\n")
            f.write("    pass\n")

        subprocess.run(["git", "add", "."], capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "remove hasattr"], capture_output=True, check=False
        )

        # Run the check script - should pass when no garbage patterns
        result = subprocess.run(["bash", script_path], capture_output=True, text=True)

        if result.returncode != 0:
            print("FAIL: check_git_diff.sh should pass when no garbage patterns")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        print("PASS: check_git_diff.sh test")
        return True

    finally:
        os.chdir(original_dir)
        shutil.rmtree(test_dir)


def main():
    """
    Run all tests for the garbage code check scripts.
    """
    tests = [
        test_check_python_comments,
        test_check_pr_body,
        test_check_git_diff,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"ERROR in {test_func.__name__}: {e}")
            failed += 1

    print(f"\nTest Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
