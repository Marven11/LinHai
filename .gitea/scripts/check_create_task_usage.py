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


def get_asyncio_aliases(tree: ast.AST) -> Set[str]:
    asyncio_names = {"asyncio"}
    create_task_names = {"create_task"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "asyncio" or (
                node.module and node.module.endswith(".asyncio")
            ):
                for alias in node.names:
                    if alias.name == "create_task":
                        name = alias.asname if alias.asname else alias.name
                        create_task_names.add(name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "asyncio":
                    if alias.asname:
                        asyncio_names.add(alias.asname)
                    else:
                        asyncio_names.add("asyncio")

    return asyncio_names


def check_create_task_usage_in_file(file_path: str) -> List[Tuple[int, int, str]]:
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"WARNING: Failed to parse {file_path}: {e}")
        return violations

    asyncio_names = get_asyncio_aliases(tree)

    create_task_direct_names = {"create_task"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "asyncio" or (
                node.module and node.module.endswith(".asyncio")
            ):
                for alias in node.names:
                    if alias.name == "create_task":
                        name = alias.asname if alias.asname else alias.name
                        create_task_direct_names.add(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in create_task_direct_names:
                    violations.append(
                        (
                            node.lineno,
                            node.col_offset,
                            f"Direct create_task call: {node.func.id}",
                        )
                    )
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == "create_task":
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id in asyncio_names:
                            violations.append(
                                (
                                    node.lineno,
                                    node.col_offset,
                                    f"asyncio.create_task call via alias: {node.func.value.id}.create_task",
                                )
                            )

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
        f"Checking {len(python_files)} changed Python file(s) for asyncio.create_task usage..."
    )

    errors_found = False
    for file_path in python_files:
        violations = check_create_task_usage_in_file(file_path)
        if violations:
            errors_found = True
            print(f"\nERROR: asyncio.create_task usage found in {file_path}:")
            for line, col, msg in violations:
                print(f"  Line {line}, Col {col}: {msg}")

    if errors_found:
        print("\nERROR: asyncio.create_task() usage detected.")
        print(
            "Please use TaskSupervisor.create_superviced_task instead of asyncio.create_task."
        )
        sys.exit(1)
    else:
        print("SUCCESS: No asyncio.create_task usage found in changed Python files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
