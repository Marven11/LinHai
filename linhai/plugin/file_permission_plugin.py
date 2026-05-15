"""文件操作权限检查插件。"""

import fnmatch

from linhai.type_hints import WithSecret
from pathlib import Path
from typing import Any

from linhai.agent.lifecycle import Lifecycle
from linhai.config import ToolConfig, FileOperationRule
from linhai.tool.base import FailedToolResult
from linhai.registry import Registry


class FileOperationPermissionPlugin:
    def __init__(self, registry: Registry, pwd: Path, tool_config: ToolConfig):
        self.registry = registry
        self.pwd = pwd
        self.rules = tool_config.file_operation_rules
        self.default_rule = tool_config.file_operation_default_rule

    def check_permission(self, operation: str, filepath: str) -> bool:
        path = Path(filepath)
        if filepath.startswith("~"):
            path = path.expanduser()
        elif not path.is_absolute():
            path = self.pwd / path
        abs_path = path.resolve()

        for rule in self.rules:
            if rule.operation == "READ" and operation != "read":
                continue
            if rule.operation == "WRITE" and operation != "write":
                continue
            if rule.operation == "READ_WRITE" and operation not in ["read", "write"]:
                continue

            pattern = rule.pattern
            if pattern.startswith("~"):
                base_dir = Path.home()
                pattern_rel = Path(pattern).expanduser().relative_to(base_dir)
                if not abs_path.is_relative_to(base_dir):
                    continue
                rel_path = abs_path.relative_to(base_dir)
                if rel_path.match(str(pattern_rel)):
                    return rule.action == "ALLOW"
            elif Path(pattern).is_absolute():
                if fnmatch.fnmatch(str(abs_path), pattern):
                    return rule.action == "ALLOW"
            else:
                if not abs_path.is_relative_to(self.pwd):
                    continue
                rel_path = abs_path.relative_to(self.pwd)
                if rel_path.match(str(pattern)):
                    return rule.action == "ALLOW"

        return self.default_rule == "ALLOW"

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict[str, Any],
        with_secret: WithSecret | None,
    ) -> FailedToolResult | None:
        file_operations = {
            "read_file": "read",
            "write_file": "write",
            "replace_file_content": "write",
            "list_files": "read",
            "list_files_glob": "read",
            "read_file_with_sed": "read",
        }

        if tool_name in file_operations:
            operation = file_operations[tool_name]
            filepath = toolcall_arguments.get("filepath", "")
            if filepath:
                if not self.check_permission(operation, filepath):
                    operation_cn = "读取" if operation == "read" else "写入"
                    return FailedToolResult(
                        content=f"用户设置禁止你{operation_cn}这个文件路径: {filepath}"
                    )
        return None

    def register(self, lifecycle: Lifecycle) -> None:
        lifecycle.before_tool_call.register(self.before_tool_call)
