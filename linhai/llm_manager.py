from __future__ import annotations

from typing import Sequence, TypedDict
import asyncio
from datetime import datetime, timedelta
from linhai.base import Message, LanguageModel, Answer
from linhai.llm import OpenAIError
from linhai.registry import Registry
from linhai.utils.common import UiNotice


class LlmStackElement(TypedDict):
    llm_name: str
    disabled_until: datetime | None
    retry_count: int


class LlmInfo(TypedDict):
    name: str
    token_limit: int | None
    support_image: bool
    is_current: bool
    is_default: bool
    error_count: int


class LlmManagerError(Exception):
    pass


class NoAvailableLlmError(LlmManagerError):
    pass


class LlmManager:

    def __init__(
        self,
        registry: Registry,
        llms: list[LanguageModel],
        llm_fallback_map: dict[str, str | None],
        llm_fallback_duration_map: dict[str, int],
        default_llm_name: str | None = None,
    ) -> None:
        self.registry = registry
        self.llms = llms
        self.llm_names = [llm.get_name() for llm in llms]

        if default_llm_name is None:
            self.default_llm_name = self.llm_names[0]
        elif default_llm_name in self.llm_names:
            self.default_llm_name = default_llm_name
        else:
            raise ValueError(
                f"\u9519\u8bef\uff1a\u9ed8\u8ba4LLM\u540d\u79f0 '{default_llm_name}' \u4e0d\u5b58\u5728\u3002\u53ef\u7528\u7684LLM\u5305\u62ec: {', '.join(self.llm_names)}"
            )

        self.llm_fallback_map: dict[str, str | None] = {}
        if llm_fallback_map is not None:
            for llm_name, fallback_name in llm_fallback_map.items():
                if llm_name not in self.llm_names:
                    raise ValueError(
                        f"\u9519\u8bef\uff1aLLM\u540d\u79f0 '{llm_name}' \u4e0d\u5b58\u5728\u3002\u53ef\u7528\u7684LLM\u5305\u62ec: {', '.join(self.llm_names)}"
                    )
                if fallback_name is not None and fallback_name not in self.llm_names:
                    raise ValueError(
                        f"\u9519\u8bef\uff1afallback LLM\u540d\u79f0 '{fallback_name}' \u4e0d\u5b58\u5728\u3002\u53ef\u7528\u7684LLM\u5305\u62ec: {', '.join(self.llm_names)}"
                    )
                self.llm_fallback_map[llm_name] = fallback_name
        for llm_name in self.llm_names:
            assert (
                llm_name in self.llm_fallback_map
            ), f"LLM\u540d\u79f0 '{llm_name}' \u672a\u5728llm_fallback_map\u4e2d\u914d\u7f6e"

        self.llm_fallback_duration_map: dict[str, int] = {}
        if llm_fallback_duration_map is not None:
            for llm_name, duration in llm_fallback_duration_map.items():
                if llm_name not in self.llm_names:
                    raise ValueError(
                        f"\u9519\u8bef\uff1aLLM\u540d\u79f0 '{llm_name}' \u4e0d\u5b58\u5728\u3002\u53ef\u7528\u7684LLM\u5305\u62ec: {', '.join(self.llm_names)}"
                    )
                if not isinstance(duration, int) or duration <= 0:
                    raise ValueError(
                        f"\u9519\u8bef\uff1aLLM '{llm_name}' \u7684fallback_duration\u5fc5\u987b\u4e3a\u6b63\u6574\u6570\uff0c\u5f97\u5230: {duration}"
                    )
                self.llm_fallback_duration_map[llm_name] = duration
        for llm_name in self.llm_names:
            if llm_name not in self.llm_fallback_duration_map:
                self.llm_fallback_duration_map[llm_name] = 120

        self.llm_stack: list[LlmStackElement] = [
            LlmStackElement(
                llm_name=self.default_llm_name, disabled_until=None, retry_count=0
            )
        ]
        self.llm_errors: dict[str, list[tuple[datetime, str]]] = {
            name: [] for name in self.llm_names
        }

        self.registry.register_member("llm_manager", self)

    def _is_llm_expired(self, disabled_until: datetime | None) -> bool:
        if disabled_until is None:
            return False
        return datetime.now() >= disabled_until

    def _cleanup_expired_llms(self) -> None:
        while len(self.llm_stack) > 1 and self._is_llm_expired(
            self.llm_stack[-1]["disabled_until"]
        ):
            self.llm_stack.pop()

    def get_current_llm(self, rotate_invalid_llm: bool = True) -> LanguageModel:
        if rotate_invalid_llm:
            self._cleanup_expired_llms()
        assert len(self.llm_stack) > 0, "llm_stack should never be empty"
        llm_name = self.llm_stack[-1]["llm_name"]
        index = self.llm_names.index(llm_name)
        return self.llms[index]

    async def switch_to_llm(self, name: str) -> None:
        if name not in self.llm_names:
            raise ValueError(
                f"\u9519\u8bef\uff1aLLM\u540d\u79f0 '{name}' \u4e0d\u5b58\u5728\u3002\u53ef\u7528\u7684LLM\u5305\u62ec: {', '.join(self.llm_names)}"
            )
        self.llm_stack = [
            LlmStackElement(llm_name=name, disabled_until=None, retry_count=0)
        ]
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content=f"\u5df2\u5207\u6362\u5230LLM: {name}"),
        )

    def _record_error(self, llm_name: str, error_type: str) -> None:
        current_time = datetime.now()
        self.llm_errors[llm_name].append((current_time, error_type))
        if len(self.llm_errors[llm_name]) > 100:
            self.llm_errors[llm_name] = self.llm_errors[llm_name][-100:]

    def _get_fallback_llm(self, llm_name: str) -> str | None:
        return self.llm_fallback_map.get(llm_name)

    async def _trigger_on_llm_error(
        self, llm_name: str, error: Exception, retry_count: int
    ) -> None:
        from linhai.agent.lifecycle import Lifecycle

        if self.registry.has_member("lifecycle"):
            lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
            await lifecycle.on_llm_error.trigger(llm_name, error, retry_count)

    async def answer_stream(self, history: Sequence[Message]) -> Answer:
        if not history:
            raise ValueError("history is empty")

        while True:
            self._cleanup_expired_llms()
            assert len(self.llm_stack) > 0, "llm_stack should never be empty"
            element = self.llm_stack[-1]
            llm_name = element["llm_name"]
            current_llm = self.llms[self.llm_names.index(llm_name)]

            try:
                answer = await current_llm.answer_stream(history)
                return answer
            except asyncio.TimeoutError as e:
                element["retry_count"] += 1
                self._record_error(llm_name, "timeout")
                delay = min(5 * 1.5 ** element["retry_count"], 300)
                await self._trigger_on_llm_error(llm_name, e, element["retry_count"])
                await self.registry.send_if_exists(
                    "ui_log",
                    UiNotice(
                        level="WARNING",
                        content=f"LLM '{llm_name}' \u8d85\u65f6\uff0c\u5c06\u5728 {delay:.1f} \u79d2\u540e\u91cd\u8bd5",
                    ),
                )
                await asyncio.sleep(delay)
            except Exception as e:
                error_str = str(e).lower()
                fallback_llm = self._get_fallback_llm(llm_name)

                if "rate limit" in error_str or "429" in error_str:
                    element["retry_count"] += 1
                    self._record_error(llm_name, "rate_limit")
                    await current_llm.reconnect()
                    await self._trigger_on_llm_error(
                        llm_name, e, element["retry_count"]
                    )
                    if fallback_llm is not None:
                        fallback_duration = self.llm_fallback_duration_map.get(
                            llm_name, 120
                        )
                        disabled_until = datetime.now() + timedelta(
                            seconds=fallback_duration
                        )
                        self.llm_stack.append(
                            LlmStackElement(
                                llm_name=fallback_llm,
                                disabled_until=disabled_until,
                                retry_count=0,
                            )
                        )
                        await self.registry.send_if_exists(
                            "ui_log",
                            UiNotice(
                                level="WARNING",
                                content=f"LLM '{llm_name}' \u901f\u7387\u9650\u5236\uff0c\u5df2\u5207\u6362\u5230fallback LLM: {fallback_llm}\uff0c{fallback_duration}s\u540e\u6062\u590d",
                            ),
                        )
                    else:
                        delay = min(5 * 1.5 ** element["retry_count"], 30)
                        await self.registry.send_if_exists(
                            "ui_log",
                            UiNotice(
                                level="WARNING",
                                content=f"LLM '{llm_name}' \u901f\u7387\u9650\u5236\uff0c\u5c06\u5728 {delay:.1f} \u79d2\u540e\u91cd\u8bd5",
                            ),
                        )
                        await asyncio.sleep(delay)
                elif "connection" in error_str or "network" in error_str:
                    element["retry_count"] += 1
                    self._record_error(llm_name, "connection")
                    await self._trigger_on_llm_error(
                        llm_name, e, element["retry_count"]
                    )
                    if fallback_llm is not None:
                        disabled_until = datetime.now() + timedelta(minutes=1)
                        self.llm_stack.append(
                            LlmStackElement(
                                llm_name=fallback_llm,
                                disabled_until=disabled_until,
                                retry_count=0,
                            )
                        )
                        await self.registry.send_if_exists(
                            "ui_log",
                            UiNotice(
                                level="WARNING",
                                content=f"LLM '{llm_name}' \u7f51\u7edc\u9519\u8bef\uff0c\u5df2\u5207\u6362\u5230fallback LLM: {fallback_llm}\uff0c1\u5206\u949f\u540e\u6062\u590d",
                            ),
                        )
                    else:
                        delay = min(5 * 1.5 ** element["retry_count"], 300)
                        await self.registry.send_if_exists(
                            "ui_log",
                            UiNotice(
                                level="WARNING",
                                content=f"LLM '{llm_name}' \u9519\u8bef: {error_str[:100]}\uff0c\u5c06\u5728 {delay:.1f} \u79d2\u540e\u91cd\u8bd5",
                            ),
                        )
                        await asyncio.sleep(delay)
                else:
                    if isinstance(e, OpenAIError):
                        element["retry_count"] += 1
                        self._record_error(llm_name, "openai_error")
                        await self._trigger_on_llm_error(
                            llm_name, e, element["retry_count"]
                        )
                        if fallback_llm is not None:
                            disabled_until = datetime.now() + timedelta(minutes=1)
                            self.llm_stack.append(
                                LlmStackElement(
                                    llm_name=fallback_llm,
                                    disabled_until=disabled_until,
                                    retry_count=0,
                                )
                            )
                            await self.registry.send_if_exists(
                                "ui_log",
                                UiNotice(
                                    level="WARNING",
                                    content=f"LLM '{llm_name}' \u9519\u8bef: {error_str[:100]}\uff0c\u5df2\u5207\u6362\u5230fallback LLM: {fallback_llm}\uff0c1\u5206\u949f\u540e\u6062\u590d",
                                ),
                            )
                        else:
                            delay = min(5 * 1.5 ** element["retry_count"], 300)
                            await self.registry.send_if_exists(
                                "ui_log",
                                UiNotice(
                                    level="WARNING",
                                    content=f"LLM '{llm_name}' \u9519\u8bef: {error_str[:100]}\uff0c\u5c06\u5728 {delay:.1f} \u79d2\u540e\u91cd\u8bd5",
                                ),
                            )
                            await asyncio.sleep(delay)
                    else:
                        raise

    def list_available_llms(self) -> list[LlmInfo]:
        current_llm = self.get_current_llm(rotate_invalid_llm=False)
        current_llm_name = current_llm.get_name() if current_llm else None
        result: list[LlmInfo] = []
        for llm, name in zip(self.llms, self.llm_names):
            result.append(
                LlmInfo(
                    name=name,
                    token_limit=llm.get_token_limit(),
                    support_image=llm.support_image(),
                    is_current=name == current_llm_name,
                    is_default=name == self.default_llm_name,
                    error_count=len(self.llm_errors[name]),
                )
            )
        return result
