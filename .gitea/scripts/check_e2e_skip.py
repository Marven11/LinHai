import ast
import os
import sys
from typing import List, Tuple

E2E_DIR = "e2e"

SKIP_DECORATORS = {"skipif", "skip"}


def get_e2e_files() -> List[str]:
    result = []
    for root, _dirs, files in os.walk(E2E_DIR):
        for fname in files:
            if fname.endswith(".py"):
                result.append(os.path.join(root, fname))
    return sorted(result)


def check_file(file_path: str) -> List[Tuple[int, str]]:
    violations: List[Tuple[int, str]] = []
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=file_path)

    pytest_skip_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "pytest":
            for alias in node.names:
                if alias.name == "skip":
                    pytest_skip_names.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                name = _get_decorator_name(deco)
                if name is None:
                    continue
                if _is_skip_decorator(name):
                    violations.append((node.lineno, f"skip decorator @{name}"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if (
                    node.func.attr == "skipTest"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self"
                ):
                    violations.append((node.lineno, "self.skipTest() call"))
                if node.func.attr == "skip" and isinstance(node.func.value, ast.Name):
                    if node.func.value.id in pytest_skip_names:
                        violations.append(
                            (
                                node.lineno,
                                f"pytest.skip() call via '{node.func.value.id}'",
                            )
                        )
            if isinstance(node.func, ast.Name):
                if node.func.id in pytest_skip_names:
                    violations.append(
                        (node.lineno, f"pytest.skip() call via '{node.func.id}'")
                    )

    return violations


def _get_decorator_name(deco: ast.expr) -> str | None:
    if isinstance(deco, ast.Name):
        return deco.id
    if isinstance(deco, ast.Attribute):
        return f"{_get_decorator_name(deco.value)}.{deco.attr}"
    if isinstance(deco, ast.Call):
        return _get_decorator_name(deco.func)
    return None


def _is_skip_decorator(name: str) -> bool:
    parts = name.split(".")
    if len(parts) >= 2:
        if parts[-1] in SKIP_DECORATORS:
            return True
    if name in ("unittest.skip", "unittest.skipIf"):
        return True
    return False


def main() -> None:
    e2e_files = get_e2e_files()
    if not e2e_files:
        print(f"No Python files found in {E2E_DIR}/")
        sys.exit(0)

    print(f"Checking {len(e2e_files)} e2e file(s) for skip patterns...")

    has_violations = False
    for file_path in e2e_files:
        violations = check_file(file_path)
        if violations:
            has_violations = True
            print(f"\nERROR: Skip patterns found in {file_path}:")
            for line, msg in violations:
                print(f"  Line {line}: {msg}")

    if has_violations:
        print(
            "\nERROR: e2e tests must not use skip mechanisms "
            "(skipif, skipTest, pytest.skip, etc)."
        )
        sys.exit(1)
    else:
        print("SUCCESS: No skip patterns found in e2e tests.")
        sys.exit(0)


if __name__ == "__main__":
    main()
