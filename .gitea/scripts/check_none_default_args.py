import sys
import os
import subprocess
import ast
from typing import List, Set, Tuple


def get_changed_python_files(base_ref: str = "origin/main") -> List[str]:
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"

        cmd = [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            base_ref,
            "HEAD",
            "--",
            "linhai/",
        ]
        output = subprocess.check_output(
            cmd, universal_newlines=True, stderr=subprocess.DEVNULL
        ).strip()

        if not output:
            return []

        files = output.split("\n")
        return [f for f in files if f.endswith(".py") and os.path.exists(f)]
    except subprocess.CalledProcessError:
        return []


def get_added_line_numbers(file_path: str, base_ref: str = "origin/main") -> Set[int]:
    added_lines: Set[int] = set()
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"

        cmd = ["git", "diff", "--unified=0", base_ref, "HEAD", "--", file_path]
        diff_output = subprocess.check_output(
            cmd, universal_newlines=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return added_lines

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
                added_lines.add(current_line_number)
                current_line_number += 1
    return added_lines


def is_none_empty_default(node: ast.expr) -> Tuple[bool, str]:
    if isinstance(node, ast.Constant):
        if node.value is None:
            return True, "None"
    if isinstance(node, ast.Dict) and not node.keys and not node.values:
        return True, "{}"
    if isinstance(node, ast.List) and not node.elts:
        return True, "[]"
    return False, ""


def check_function_defaults(
    node: ast.FunctionDef,
    added_lines: Set[int],
    violations: List[Tuple[int, str, str]],
) -> None:
    args = node.args
    num_defaults = len(args.defaults)
    num_args = len(args.args)
    for i, default_node in enumerate(args.defaults):
        is_bad, default_str = is_none_empty_default(default_node)
        if is_bad:
            arg_index = num_args - num_defaults + i
            arg_name = args.args[arg_index].arg
            if default_node.lineno in added_lines:
                violations.append((default_node.lineno, arg_name, default_str))

    for i, default_node in enumerate(args.kw_defaults):
        if default_node is None:
            continue
        is_bad, default_str = is_none_empty_default(default_node)
        if is_bad:
            arg_name = args.kwonlyargs[i].arg
            if default_node.lineno in added_lines:
                violations.append((default_node.lineno, arg_name, default_str))


def check_file(
    file_path: str, base_ref: str = "origin/main"
) -> List[Tuple[int, str, str]]:
    violations: List[Tuple[int, str, str]] = []
    added_lines = get_added_line_numbers(file_path, base_ref)
    if not added_lines:
        return violations

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"WARNING: Failed to parse {file_path}: {e}")
        return violations

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_function_defaults(node, added_lines, violations)

    return violations


def main() -> None:
    base_ref = os.environ.get("BASE_REF")
    if base_ref:
        base_ref = f"origin/{base_ref}"
    else:
        base_ref = "origin/main"

    python_files = get_changed_python_files(base_ref)

    if not python_files:
        print("No Python files changed in linhai/ directory.")
        sys.exit(0)

    print(
        f"Checking {len(python_files)} changed Python file(s) for None/empty default arguments..."
    )

    errors_found = False
    for file_path in python_files:
        violations = check_file(file_path, base_ref)
        if violations:
            errors_found = True
            print(f"\nERROR: None/empty default arguments found in {file_path}:")
            for line, arg_name, default_str in violations:
                print(
                    f"  Line {line}: Parameter '{arg_name}' has default value {default_str}"
                )

    if errors_found:
        print("\nERROR: Using None/{}/[] as default parameter values is forbidden.")
        print("This avoids forgetting to pass parameters. If a parameter can")
        print("legitimately be None, mark it as Optional and have the caller")
        print("pass it explicitly to confirm the intent.")
        sys.exit(1)
    else:
        print("SUCCESS: No None/empty default arguments found in changed Python files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
