"""Completion logic for CLI."""

from typing import List, Optional
from textual.widgets import Input, TextArea
from linhai.agent import Agent


class CompletionManager:
    """Manager for completion functionality."""

    def __init__(self, group_chat):
        self.group_chat = group_chat
        self.candidate_list = None
        self.completion_prefix = ""  # @或/
        self.completion_candidates: List[str] = []
        self.completion_active = False
        self.just_completed_candidate = False  # 标记是否刚刚完成候选选择

    def get_completion_candidates(self, prefix: str, _current_text: str) -> List[str]:
        """获取补全候选项"""
        if prefix == "@":
            # 获取配置的LLM名称列表
            agent = self.group_chat.get_members("agent", Agent)
            return agent.context.get("llm_names", [])
        elif prefix == "/":
            # 获取可用的命令列表
            return ["queue", "quit", "exit"]
        return []

    def show_completion_list(self, prefix: str, candidates: List[str]) -> None:
        """显示候选列表"""
        if not candidates:
            self.hide_completion_list()
            return

        self.completion_prefix = prefix
        self.completion_candidates = candidates
        self.completion_active = True

    def hide_completion_list(self) -> None:
        """隐藏候选列表"""
        self.completion_active = False

    def handle_input_change(self, value: str) -> Optional[List[str]]:
        """处理输入框内容变化，返回需要显示的候选列表"""
        if not value:
            self.hide_completion_list()
            return None

        # 检查是否以@或/开头
        if value.startswith("@"):
            # 提取@后面的文本，处理@后面是空格的情况
            parts = value[1:].split()
            after_at = parts[0] if parts else ""
            candidates = self.get_completion_candidates("@", after_at)
            # 过滤匹配的候选项
            if after_at:
                candidates = [c for c in candidates if c.startswith(after_at)]
            # 如果输入中包含空格，说明LLM名称已输入完毕，隐藏候选列表
            if " " in value:
                self.hide_completion_list()
                return None
            else:
                self.show_completion_list("@", candidates)
                return candidates
        elif value.startswith("/"):
            # 提取/后面的文本，处理/后面是空格的情况
            parts = value[1:].split()
            after_slash = parts[0] if parts else ""
            candidates = self.get_completion_candidates("/", after_slash)
            # 过滤匹配的候选项
            if after_slash:
                candidates = [c for c in candidates if c.startswith(after_slash)]
            # 如果输入中包含空格，说明命令已输入完毕，隐藏候选列表
            if " " in value:
                self.hide_completion_list()
                return None
            else:
                self.show_completion_list("/", candidates)
                return candidates
        else:
            self.hide_completion_list()
            return None

    def handle_key_event(self, event_key: str, _input_widget: Input | TextArea) -> bool:
        """处理键盘事件，返回是否处理了事件"""
        if not self.completion_active:
            return False

        if event_key == "up":
            # 上箭头：向上移动（索引增加）
            return True
        elif event_key == "down":
            # 下箭头：向下移动（索引减少）
            return True
        elif event_key in ["tab", "enter"]:
            # 选择当前候选项
            # 标记刚刚完成候选选择，忽略接下来的提交事件
            self.just_completed_candidate = True
            self.hide_completion_list()
            return True
        elif event_key == "escape":
            # 取消补全
            self.hide_completion_list()
            return True

        return False