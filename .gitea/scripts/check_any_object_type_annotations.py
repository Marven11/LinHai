import sys
import os
import subprocess
import ast
from typing import List, Set, Tuple, Optional, Dict


def get_any_aliases(tree: ast.AST) -> Set[str]:
    """Extract all aliases for typing.Any from import statements."""
    aliases: Set[str] = {"Any"}
    typing_module_names: Set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "typing":
                for alias in node.names:
                    if alias.name == "Any":
                        if alias.asname:
                            aliases.add(alias.asname)
            elif node.module and node.module.startswith("typing."):
                for alias in node.names:
                    if alias.name == "Any":
                        if alias.asname:
                            aliases.add(alias.asname)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "typing" or alias.name.startswith("typing."):
                    typing_module_names.add(alias.asname or alias.name)

    return aliases


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


def is_any_or_object_annotation(
    node: ast.AST, any_aliases: Set[str]
) -> Tuple[bool, str]:
    if isinstance(node, ast.Name):
        if node.id in any_aliases:
            if node.id == "Any":
                return True, "Any"
            else:
                return True, f"Any (imported as '{node.id}')"
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
    node: ast.FunctionDef, violations: List[Tuple[int, str, str]], any_aliases: Set[str]
) -> None:
    for arg in node.args.args:
        if arg.annotation:
            is_invalid, type_name = is_any_or_object_annotation(
                arg.annotation, any_aliases
            )
            if is_invalid:
                violations.append((arg.lineno, arg.arg, type_name))

    for arg in node.args.kwonlyargs:
        if arg.annotation:
            is_invalid, type_name = is_any_or_object_annotation(
                arg.annotation, any_aliases
            )
            if is_invalid:
                violations.append((arg.lineno, arg.arg, type_name))

    if node.args.vararg and node.args.vararg.annotation:
        is_invalid, type_name = is_any_or_object_annotation(
            node.args.vararg.annotation, any_aliases
        )
        if is_invalid:
            violations.append(
                (node.args.vararg.lineno, node.args.vararg.arg, type_name)
            )

    if node.args.kwarg and node.args.kwarg.annotation:
        is_invalid, type_name = is_any_or_object_annotation(
            node.args.kwarg.annotation, any_aliases
        )
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

    any_aliases = get_any_aliases(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            check_function_args(node, violations, any_aliases)
        elif isinstance(node, ast.AsyncFunctionDef):
            check_function_args(node, violations, any_aliases)

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
        print("Using type aliases (e.g., 'from typing import Any as XXX') to bypass")
        print("detection is FORBIDDEN and violates the code standards.")
        print("\nPlease use specific types instead of Any or object.")
        print("Examples:")
        print("  def foo(x: int) -> str:      # Good")
        print("  def bar(x: Optional[int]) -> None:  # Good")
        print("  def baz(x: Any) -> None:    # BAD")
        print("  def qux(x: XXX) -> None:    # BAD (where XXX is an alias for Any)")
        sys.exit(1)
    else:
        print("SUCCESS: No Any/object type annotations found in changed Python files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
