import sys
import os
import subprocess
import ast
from typing import List, Set, Tuple, Optional


def get_changed_python_files(base_ref: str = "origin/main") -> List[str]:
    try:
        check_cmd = ["git", "rev-parse", "--verify", base_ref]
        if subprocess.run(check_cmd, capture_output=True).returncode != 0:
            base_ref = "HEAD^"

        cmd = [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=d",
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


def is_any_or_object_annotation(node: ast.AST) -> Tuple[bool, str]:
    if isinstance(node, ast.Name):
        if node.id == "Any":
            return True, "Any"
        if node.id == "object":
            return True, "object"
    elif isinstance(node, ast.Attribute):
        if (
            node.attr == "Any"
            and isinstance(node.value, ast.Name)
            and node.value.id == "typing"
        ):
            return True, "typing.Any"
        if (
            node.attr == "Object"
            and isinstance(node.value, ast.Name)
            and node.value.id == "typing"
        ):
            return True, "typing.Object"
    return False, ""


def check_function_args(
    node: ast.FunctionDef, violations: List[Tuple[int, str, str]]
) -> None:
    for arg in node.args.args:
        if arg.annotation:
            is_invalid, type_name = is_any_or_object_annotation(arg.annotation)
            if is_invalid:
                violations.append((arg.lineno, arg.arg, type_name))

    for arg in node.args.kwonlyargs:
        if arg.annotation:
            is_invalid, type_name = is_any_or_object_annotation(arg.annotation)
            if is_invalid:
                violations.append((arg.lineno, arg.arg, type_name))

    if node.args.vararg and node.args.vararg.annotation:
        is_invalid, type_name = is_any_or_object_annotation(node.args.vararg.annotation)
        if is_invalid:
            violations.append(
                (node.args.vararg.lineno, node.args.vararg.arg, type_name)
            )

    if node.args.kwarg and node.args.kwarg.annotation:
        is_invalid, type_name = is_any_or_object_annotation(node.args.kwarg.annotation)
        if is_invalid:
            violations.append((node.args.kwarg.lineno, node.args.kwarg.arg, type_name))


def check_any_object_in_file(file_path: str) -> List[Tuple[int, str, str]]:
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"WARNING: Failed to parse {file_path}: {e}")
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            check_function_args(node, violations)
        elif isinstance(node, ast.AsyncFunctionDef):
            check_function_args(node, violations)

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
        f"Checking {len(python_files)} changed Python file(s) for Any/object type annotations..."
    )

    errors_found = False
    for file_path in python_files:
        violations = check_any_object_in_file(file_path)
        if violations:
            errors_found = True
            print(f"\nERROR: Any/object type annotations found in {file_path}:")
            for line, arg_name, type_name in violations:
                print(
                    f"  Line {line}: Parameter '{arg_name}' has type annotation '{type_name}'"
                )

    if errors_found:
        print(
            "\nERROR: Any or object type annotations detected in function parameters."
        )
        print("Please use specific types instead of Any or object.")
        sys.exit(1)
    else:
        print("SUCCESS: No Any/object type annotations found in changed Python files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
