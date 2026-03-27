import sys
import os
import subprocess
import ast
from typing import List, Set, Tuple, Optional


def get_changed_python_files(base_ref: str = "origin/main") -> List[str]:
    """
    Get list of changed Python files in the diff.
    """
    try:
        # Check if base_ref exists, fallback to HEAD^
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


def get_import_aliases(tree: ast.AST) -> Set[str]:
    """
    Extract all import aliases for 'cast' from the AST.
    Returns set of names that refer to cast function.
    """
    cast_names = {"cast"}  # Always include 'cast' as a base name

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "typing" or (
                node.module and node.module.endswith(".typing")
            ):
                for alias in node.names:
                    if alias.name == "cast":
                        if alias.asname:
                            cast_names.add(alias.asname)
                        else:
                            cast_names.add("cast")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "typing":
                    # import typing - we'll need to check typing.cast
                    pass
                elif alias.name == "cast":
                    if alias.asname:
                        cast_names.add(alias.asname)
                    else:
                        cast_names.add("cast")

    return cast_names


def check_cast_usage_in_file(file_path: str) -> List[Tuple[int, int, str]]:
    """
    Check a Python file for cast usage.
    Returns list of violations as (line, col, message).
    """
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"WARNING: Failed to parse {file_path}: {e}")
        return violations

    # Get all names that refer to cast function
    cast_names = get_import_aliases(tree)

    # Walk AST to find cast calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check for direct cast call: cast(Type, value)
            if isinstance(node.func, ast.Name):
                if node.func.id in cast_names:
                    violations.append(
                        (
                            node.lineno,
                            node.col_offset,
                            f"Direct cast call: {node.func.id}",
                        )
                    )

            # Check for typing.cast call
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == "cast":
                    # Check if it's typing.cast or something.typing.cast
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "typing":
                            violations.append(
                                (node.lineno, node.col_offset, "typing.cast call")
                            )
                    elif isinstance(node.func.value, ast.Attribute):
                        # Handle cases like module.typing.cast
                        if isinstance(node.func.value.value, ast.Name):
                            if (
                                node.func.value.value.id + "." + node.func.value.attr
                                == "typing"
                            ):
                                violations.append(
                                    (node.lineno, node.col_offset, "typing.cast call")
                                )

    return violations


def main() -> None:
    """
    Main function to check all changed Python files for cast usage.
    """
    base_ref = os.environ.get("BASE_REF")
    if base_ref:
        base_ref = f"origin/{base_ref}"
    else:
        base_ref = "origin/main"

    python_files = get_changed_python_files(base_ref)

    if not python_files:
        print("No Python files changed in linhai/ directory.")
        sys.exit(0)

    print(f"Checking {len(python_files)} changed Python file(s) for cast usage...")

    errors_found = False
    for file_path in python_files:
        violations = check_cast_usage_in_file(file_path)
        if violations:
            errors_found = True
            print(f"\nERROR: Cast usage found in {file_path}:")
            for line, col, msg in violations:
                print(f"  Line {line}, Col {col}: {msg}")

    if errors_found:
        print("\nERROR: cast() or typing.cast() usage detected.")
        print(
            "Please avoid using cast for type assertions. Use proper type hints instead."
        )
        sys.exit(1)
    else:
        print("SUCCESS: No cast usage found in changed Python files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
