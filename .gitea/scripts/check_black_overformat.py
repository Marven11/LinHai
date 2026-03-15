import sys
import subprocess
import tempfile
import os


def get_changed_py_files(base_ref="origin/main"):
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
        cmd = ["git", "diff", "--name-only", base_ref, "HEAD", "--", "linhai/"]
        output = subprocess.check_output(
            cmd, universal_newlines=True, stderr=subprocess.DEVNULL
        )
        files = [f for f in output.strip().split("\n") if f and f.endswith(".py")]
        return files
    except subprocess.CalledProcessError:
        return []


def check_black_overformat(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original = f.read()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(original)
            tmp_path = tmp.name

        cmd = ["uv", "run", "black", "--quiet", tmp_path]
        subprocess.run(cmd, capture_output=True, check=True)

        with open(tmp_path, "r", encoding="utf-8") as f:
            formatted = f.read()

        os.unlink(tmp_path)

        if original != formatted:
            original_lines = original.split("\n")
            formatted_lines = formatted.split("\n")

            diff_count = 0
            for i, (orig, fmt) in enumerate(zip(original_lines, formatted_lines)):
                if orig != fmt:
                    stripped_orig = orig.rstrip()
                    stripped_fmt = fmt.rstrip()
                    if stripped_orig == stripped_fmt:
                        diff_count += 1

            if diff_count > len(original_lines) * 0.3:
                return True
        return False
    except Exception:
        return False


def main():
    base_ref = "origin/main"
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"
    except Exception:
        base_ref = "HEAD^"

    files = get_changed_py_files(base_ref)
    if not files:
        print("No Python files changed in linhai/ directory.")
        sys.exit(0)

    errors = []
    for file_path in files:
        if check_black_overformat(file_path):
            errors.append(file_path)

    if errors:
        print("ERROR: Black appears to be overformatting these files:")
        for err in errors:
            print(f"  {err}")
        print("\nPlease check if black is making excessive formatting changes.")
        sys.exit(1)
    else:
        print("SUCCESS: No black overformatting detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
