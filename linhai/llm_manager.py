from __future__ import annotations
from typing import Sequence
import asyncio
from datetime import datetime, timedelta
from linhai.llm import Message, LanguageModel, Answer, OpenAi
from linhai.group_chat import GroupChat
from linhai.utils import CliRuntimeNotice


class LlmManagerError(Exception):
    """基类异常，用于LlmManager相关错误"""


class NoAvailableLlmError(LlmManagerError):
    """所有LLM都被禁用时的异常"""


class LlmManager:
    """统一管理多个LLM实例，处理错误重试和自动切换"""

    def __init__(
        self,
        group_chat: GroupChat,
        llms: list[LanguageModel],
        default_llm_name: str | None = None,
        max_retries_per_llm: int = 3,
    ) -> None:
        """初始化LlmManager

        Args:
            group_chat: GroupChat实例，用于消息通信
            llms: LanguageModel实例列表
            default_llm_name: 默认LLM名称，如果为None则使用第一个LLM
            max_retries_per_llm: 每个LLM的最大重试次数

        """
        self.group_chat = group_chat
        self.llms = llms
        self.llm_names = [llm.get_name() for llm in llms]

        if default_llm_name is None:
            self.default_llm_index = 0
        elif default_llm_name in self.llm_names:
            self.default_llm_index = self.llm_names.index(default_llm_name)
        else:
            raise ValueError(
                f"错误：默认LLM名称 '{default_llm_name}' 不存在。可用的LLM包括: {', '.join(self.llm_names)}"
            )

        self.current_llm_index = self.default_llm_index
        self.max_retries_per_llm = max_retries_per_llm

        self.llm_errors: dict[str, list[tuple[datetime, str]]] = {
            name: [] for name in self.llm_names
        }
        self.llm_disabled_until: dict[str, datetime | None] = {
            name: None for name in self.llm_names
        }

        self.group_chat.register_member("llm_manager", self)

    def get_current_llm(self) -> LanguageModel:
        """获取当前使用的LLM实例

        Returns:
            LanguageModel: 当前LLM实例
        """
        return self.llms[self.current_llm_index]

    async def switch_to_llm(self, name: str) -> None:
        """切换到指定的LLM

        Args:
            name: 目标LLM名称

        Raises:
            ValueError: 如果指定的LLM名称不存在
        """
        if name not in self.llm_names:
            raise ValueError(
                f"错误：LLM名称 '{name}' 不存在。可用的LLM包括: {', '.join(self.llm_names)}"
            )
        self.current_llm_index = self.llm_names.index(name)
        await self.group_chat.send_if_exists(
            "ui_log", CliRuntimeNotice(level="INFO", content=f"已切换到LLM: {name}")
        )

    def _record_error(self, llm_name: str, error_type: str) -> None:
        """记录LLM错误

        Args:
            llm_name: LLM名称
            error_type: 错误类型
        """
        current_time = datetime.now()
        self.llm_errors[llm_name].append((current_time, error_type))
        if len(self.llm_errors[llm_name]) > 100:
            self.llm_errors[llm_name] = self.llm_errors[llm_name][-100:]
        if error_type == "rate_limit" or "429" in error_type:
            disable_until = current_time + timedelta(minutes=5)
            self.llm_disabled_until[llm_name] = disable_until

    def _is_llm_disabled(self, llm_name: str) -> bool:
        """检查LLM是否被禁用

        Args:
            llm_name: LLM名称

        Returns:
            bool: 如果LLM被禁用则返回True，否则返回False
        """
        disabled_until = self.llm_disabled_until[llm_name]
        if disabled_until is None:
            return False
        if datetime.now() >= disabled_until:
            self.llm_disabled_until[llm_name] = None
            return False
        return True

    def _get_next_available_llm(self) -> LanguageModel:
        """获取下一个可用的LLM

        如果所有LLM都被禁用，则不断重试第一个LLM

        Returns:
            LanguageModel: 可用的LLM实例
        """
        start_index = self.current_llm_index
        checked = 0
        while checked < len(self.llms):
            index = (start_index + 1) % len(self.llms)
            llm_name = self.llm_names[index]
            if not self._is_llm_disabled(llm_name):
                self.current_llm_index = index
                return self.llms[index]
            start_index = index
            checked += 1

        self.current_llm_index = 0
        return self.llms[0]

    async def answer_stream(self, history: Sequence[Message]) -> Answer:
        """生成流式回答

        Args:
            history: 消息历史序列

        Returns:
            Answer: 生成的回答

        Raises:
            ValueError: 如果历史为空
            RuntimeError: 如果重试次数耗尽仍无法完成
        """
        if not history:
            raise ValueError("history is empty")

        retry_count = 0
        last_error = None

        while retry_count < self.max_retries_per_llm:
            current_llm = self.get_current_llm()
            current_llm_name = self.llm_names[self.current_llm_index]

            if self._is_llm_disabled(current_llm_name):
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING",
                        content=f"LLM '{current_llm_name}' 被禁用，正在切换到下一个可用LLM",
                    ),
                )
                current_llm = self._get_next_available_llm()
                current_llm_name = self.llm_names[self.current_llm_index]
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="INFO", content=f"已切换到LLM: {current_llm_name}"
                    ),
                )

            try:
                answer = await current_llm.answer_stream(history)
                return answer
            except asyncio.TimeoutError as e:
                last_error = e
                self._record_error(current_llm_name, "timeout")
                delay = min(1.5**retry_count, 300)
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING",
                        content=f"LLM '{current_llm_name}' 超时，将在 {delay:.1f} 秒后重试",
                    ),
                )
                await asyncio.sleep(delay)
                retry_count += 1
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "rate limit" in error_str or "429" in error_str:
                    self._record_error(current_llm_name, "rate_limit")
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content=f"LLM '{current_llm_name}' 速率限制，将切换到下一个LLM",
                        ),
                    )
                    current_llm = self._get_next_available_llm()
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="INFO",
                            content=f"已切换到LLM: {self.llm_names[self.current_llm_index]}",
                        ),
                    )
                    continue
                elif "connection" in error_str or "network" in error_str:
                    error_type = "connection"
                else:
                    error_type = "unknown"

                self._record_error(current_llm_name, error_type)
                delay = min(1.5**retry_count, 300)
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING",
                        content=f"LLM '{current_llm_name}' 错误: {error_str[:100]}，将在 {delay:.1f} 秒后重试",
                    ),
                )
                await asyncio.sleep(delay)
                retry_count += 1

        raise RuntimeError(
            f"LLM处理失败，重试{self.max_retries_per_llm}次后仍无法完成: {last_error}"
        )

    def list_available_llms(self) -> list[dict[str, object]]:
        """列出所有可用的LLM及其状态

        Returns:
            list[dict]: LLM信息列表，每个字典包含以下键：
                - name: LLM名称
                - model: 模型名称
                - token_limit: token限制
                - support_image: 是否支持图像
                - is_current: 是否是当前使用的LLM
                - is_default: 是否是默认LLM
                - is_disabled: 是否被禁用
                - disabled_until: 禁用截止时间
                - error_count: 错误计数
        """
        result = []
        for i, (llm, name) in enumerate(zip(self.llms, self.llm_names)):
            model_name = "unknown"
            if isinstance(llm, OpenAi):
                model_name = llm.model

            result.append(
                {
                    "name": name,
                    "model": model_name,
                    "token_limit": llm.get_token_limit(),
                    "support_image": llm.support_image(),
                    "is_current": i == self.current_llm_index,
                    "is_default": i == self.default_llm_index,
                    "is_disabled": self._is_llm_disabled(name),
                    "disabled_until": self.llm_disabled_until[name],
                    "error_count": len(self.llm_errors[name]),
                }
            )
        return result
