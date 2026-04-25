from typing import TypedDict

from linhai.base import UserMessage
from linhai.utils.input_parser import ParsedInput, parse_user_input
from linhai.registry import Registry


class ParsedUserMessage(TypedDict):
    raw_message: UserMessage
    parsed_input: ParsedInput


class UserMessageHandler:
    def __init__(self, registry: Registry):
        self.registry = registry
        self.registry.register_member("user_message_handler", self)

    def has_message(self) -> bool:
        return not self.registry.is_empty("user_message")

    async def receive_and_dispatch(self) -> bool:
        msg = await self.registry.receive("user_message")
        assert isinstance(msg, UserMessage)
        parsed_input = parse_user_input(msg.message.strip())
        parsed = ParsedUserMessage(raw_message=msg, parsed_input=parsed_input)

        from .lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        result = await lifecycle.after_parsed_user_message.trigger(parsed)
        if result is not None:
            return result

        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        await agent.message_processor.add_new_message(msg)
        return True

    def serialize(self) -> dict:
        return {}

    def restore_from(self, data: dict) -> None:
        pass
