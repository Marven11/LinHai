import sys
import os
import subprocess
import ast
from typing import Dict, List, Set, Tuple

_added_lines_cache: Dict[str, Dict[str, Set[int]]] = {}


def _resolve_base_ref(base_ref: str) -> str:
    check_cmd = ["git", "rev-parse", "--verify", base_ref]
    if subprocess.run(check_cmd, capture_output=True).returncode != 0:
        return "HEAD^"
    return base_ref


def _ensure_diff_cache(base_ref: str) -> None:
    if base_ref in _added_lines_cache:
        return
    resolved = _resolve_base_ref(base_ref)
    cmd = ["git", "diff", "-M", "--unified=0", resolved, "HEAD", "--", "linhai/"]
    try:
        output = subprocess.check_output(
            cmd, universal_newlines=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        _added_lines_cache[base_ref] = {}
        return

    result: Dict[str, Set[int]] = {}
    current_file = None
    current_line_number = None
    for line in output.split("\n"):
        if line.startswith("diff --git "):
            parts = line.split(" b/")
            if len(parts) >= 2:
                current_file = parts[-1].strip()
        elif line.startswith("+++ b/"):
            current_file = line[6:].strip()
        elif line.startswith("@@"):
            parts = line.split(" ")
            for part in parts:
                if part.startswith("+"):
                    try:
                        current_line_number = int(part[1:].split(",")[0])
                    except ValueError:
                        pass
                    break
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file and current_line_number is not None:
                result.setdefault(current_file, set()).add(current_line_number)
                current_line_number += 1
    _added_lines_cache[base_ref] = result


def get_changed_python_files(base_ref: str = "origin/main") -> List[str]:
    try:
        resolved = _resolve_base_ref(base_ref)
        cmd = [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            resolved,
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
    _ensure_diff_cache(base_ref)
    return _added_lines_cache.get(base_ref, {}).get(file_path, set())


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
