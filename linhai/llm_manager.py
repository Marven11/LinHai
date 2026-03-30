from __future__ import annotations
from typing import Sequence
import random
import asyncio
from datetime import datetime, timedelta
from linhai.llm import Message, LanguageModel, Answer, OpenAi, OpenAIError
from linhai.registry import Registry
from linhai.utils import CliRuntimeNotice


class LlmManagerError(Exception):
    """基类异常，用于LlmManager相关错误"""


class NoAvailableLlmError(LlmManagerError):
    """所有LLM都被禁用时的异常"""


class LlmManager:
    """统一管理多个LLM实例，处理错误重试和自动切换"""

    def __init__(
        self,
        registry: Registry,
        llms: list[LanguageModel],
        llm_fallback_map: dict[str, str | None],
        default_llm_name: str | None = None,
    ) -> None:
        """初始化LlmManager

        Args:
            registry: Registry实例，用于消息通信
            llms: LanguageModel实例列表
            default_llm_name: 默认LLM名称，如果为None则使用第一个LLM
            llm_fallback_map: LLM fallback映射，key为LLM名称，value为fallback的LLM名称

        """
        self.registry = registry
        self.llms = llms
        self.llm_names = [llm.get_name() for llm in llms]

        if default_llm_name is None:
            self.default_llm_name = self.llm_names[0]
        elif default_llm_name in self.llm_names:
            self.default_llm_name = default_llm_name
        else:
            raise ValueError(
                f"错误：默认LLM名称 '{default_llm_name}' 不存在。可用的LLM包括: {', '.join(self.llm_names)}"
            )

        self.llm_fallback_map: dict[str, str | None] = {}
        if llm_fallback_map is not None:
            for llm_name, fallback_name in llm_fallback_map.items():
                if llm_name not in self.llm_names:
                    raise ValueError(
                        f"错误：LLM名称 '{llm_name}' 不存在。可用的LLM包括: {', '.join(self.llm_names)}"
                    )
                if fallback_name is not None and fallback_name not in self.llm_names:
                    raise ValueError(
                        f"错误：fallback LLM名称 '{fallback_name}' 不存在。可用的LLM包括: {', '.join(self.llm_names)}"
                    )
                self.llm_fallback_map[llm_name] = fallback_name
        for llm_name in self.llm_names:
            assert (
                llm_name in self.llm_fallback_map
            ), f"LLM名称 '{llm_name}' 未在llm_fallback_map中配置"

        self.llm_stack: list[tuple[str, datetime | None]] = [
            (self.default_llm_name, None)
        ]
        self.llm_errors: dict[str, list[tuple[datetime, str]]] = {
            name: [] for name in self.llm_names
        }

        self.registry.register_member("llm_manager", self)

    def _is_llm_expired(self, disabled_until: datetime | None) -> bool:
        """检查LLM是否已过期

        Args:
            disabled_until: 禁用截止时间，None表示永不过期

        Returns:
            bool: 如果LLM已过期则返回True，否则返回False
        """
        if disabled_until is None:
            return False
        return datetime.now() >= disabled_until

    def _cleanup_expired_llms(self) -> None:
        """清理栈中过期的LLM，但永远保留至少一个元素"""
        while len(self.llm_stack) > 1 and self._is_llm_expired(self.llm_stack[-1][1]):
            self.llm_stack.pop()

    def get_current_llm(self) -> LanguageModel:
        """获取当前使用的LLM实例

        Returns:
            LanguageModel: 当前LLM实例
        """
        self._cleanup_expired_llms()
        assert len(self.llm_stack) > 0, "llm_stack should never be empty"
        llm_name = self.llm_stack[-1][0]
        index = self.llm_names.index(llm_name)
        return self.llms[index]

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
        self.llm_stack = [(name, None)]
        await self.registry.send_if_exists(
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

    def _get_fallback_llm(self, llm_name: str) -> str | None:
        """获取LLM的fallback配置

        Args:
            llm_name: LLM名称

        Returns:
            fallback的LLM名称，如果没有配置则返回None
        """
        return self.llm_fallback_map.get(llm_name)

    async def answer_stream(self, history: Sequence[Message]) -> Answer:
        """生成流式回答

        Args:
            history: 消息历史序列

        Returns:
            Answer: 生成的回答

        Raises:
            ValueError: 如果历史为空
            NoAvailableLlmError: 如果栈为空（理论上不可能）
        """
        if not history:
            raise ValueError("history is empty")

        retry_count = 0
        last_error = None

        while True:
            self._cleanup_expired_llms()
            assert len(self.llm_stack) > 0, "llm_stack should never be empty"
            current_llm_name = self.llm_stack[-1][0]
            current_llm = self.llms[self.llm_names.index(current_llm_name)]

            try:
                answer = await current_llm.answer_stream(history)
                return answer
            except asyncio.TimeoutError as e:
                last_error = e
                self._record_error(current_llm_name, "timeout")
                delay = min(5 * 1.5**retry_count, 300)
                await self.registry.send_if_exists(
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
                fallback_llm = self._get_fallback_llm(current_llm_name)

                if "rate limit" in error_str or "429" in error_str:
                    self._record_error(current_llm_name, "rate_limit")
                    if fallback_llm is not None:
                        disabled_duration = timedelta(
                            minutes=1, seconds=random.randint(0, 30)
                        )
                        disabled_until = datetime.now() + disabled_duration
                        self.llm_stack.append((fallback_llm, disabled_until))
                        await self.registry.send_if_exists(
                            "ui_log",
                            CliRuntimeNotice(
                                level="WARNING",
                                content=f"LLM '{current_llm_name}' 速率限制，已切换到fallback LLM: {fallback_llm}，{disabled_duration.seconds}s后恢复",
                            ),
                        )
                    else:
                        delay = min(5 * 1.5**retry_count, 300)
                        await self.registry.send_if_exists(
                            "ui_log",
                            CliRuntimeNotice(
                                level="WARNING",
                                content=f"LLM '{current_llm_name}' 速率限制，将在 {delay:.1f} 秒后重试",
                            ),
                        )
                        await asyncio.sleep(delay)
                        retry_count += 1
                elif "connection" in error_str or "network" in error_str:
                    self._record_error(current_llm_name, "connection")
                    if fallback_llm is not None:
                        disabled_until = datetime.now() + timedelta(minutes=1)
                        self.llm_stack.append((fallback_llm, disabled_until))
                        await self.registry.send_if_exists(
                            "ui_log",
                            CliRuntimeNotice(
                                level="WARNING",
                                content=f"LLM '{current_llm_name}' 网络错误，已切换到fallback LLM: {fallback_llm}，1分钟后恢复",
                            ),
                        )
                    else:
                        delay = min(5 * 1.5**retry_count, 300)
                        await self.registry.send_if_exists(
                            "ui_log",
                            CliRuntimeNotice(
                                level="WARNING",
                                content=f"LLM '{current_llm_name}' 错误: {error_str[:100]}，将在 {delay:.1f} 秒后重试",
                            ),
                        )
                        await asyncio.sleep(delay)
                        retry_count += 1
                else:
                    if isinstance(e, OpenAIError):
                        self._record_error(current_llm_name, "openai_error")
                        if fallback_llm is not None:
                            disabled_until = datetime.now() + timedelta(minutes=1)
                            self.llm_stack.append((fallback_llm, disabled_until))
                            await self.registry.send_if_exists(
                                "ui_log",
                                CliRuntimeNotice(
                                    level="WARNING",
                                    content=f"LLM '{current_llm_name}' 错误: {error_str[:100]}，已切换到fallback LLM: {fallback_llm}，1分钟后恢复",
                                ),
                            )
                        else:
                            delay = min(5 * 1.5**retry_count, 300)
                            await self.registry.send_if_exists(
                                "ui_log",
                                CliRuntimeNotice(
                                    level="WARNING",
                                    content=f"LLM '{current_llm_name}' 错误: {error_str[:100]}，将在 {delay:.1f} 秒后重试",
                                ),
                            )
                            await asyncio.sleep(delay)
                            retry_count += 1
                    else:
                        raise

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
                - error_count: 错误计数
        """
        self._cleanup_expired_llms()
        current_llm_name = self.llm_stack[-1][0] if self.llm_stack else None
        result = []
        for llm, name in zip(self.llms, self.llm_names):
            model_name = "unknown"
            if isinstance(llm, OpenAi):
                model_name = llm.model

            result.append(
                {
                    "name": name,
                    "model": model_name,
                    "token_limit": llm.get_token_limit(),
                    "support_image": llm.support_image(),
                    "is_current": name == current_llm_name,
                    "is_default": name == self.default_llm_name,
                    "error_count": len(self.llm_errors[name]),
                }
            )
        return result
