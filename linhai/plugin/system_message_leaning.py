import os
from .message_checkers import Plugin


class MachineControlIntroductionPlugin(Plugin):

    async def before_message_generation(self):
        from ..machine_control import MachineControl
        from ..base import SystemMessage

        machine_control = self.registry.get_member_typechecked(
            "machine_control", MachineControl
        )
        system_message = self.registry.get_member_typechecked(
            "system_message", SystemMessage
        )
        machine_count = len(machine_control.machines)
        title = "MACHINE CONTROL"
        from linhai.prompt import INTRODUCTION_MACHINE_CONTROL

        if machine_count > 1:
            found = any(item[0] == title for item in system_message.introduction_items)
            if not found:
                system_message.add_introduction(title, INTRODUCTION_MACHINE_CONTROL)
        else:
            system_message.remove_introduction(title)

    def register(self, lifecycle):
        lifecycle.before_message_generation.register(self.before_message_generation)


class CurrentDirectoryPlugin(Plugin):

    def __init__(self, registry):
        super().__init__(registry)
        self._has_added = False

    async def _before_agent_loop(self, agent):
        if self._has_added:
            return
        self._has_added = True
        from linhai.agent.messages import RuntimeMessage

        cwd = os.getcwd()
        await agent.message_processor.add_new_message(
            RuntimeMessage(f"当前目录为{cwd}")
        )

    def register(self, lifecycle):
        lifecycle.before_agent_loop.register(self._before_agent_loop)


class CustomToolcallFormatPlugin(Plugin):

    async def after_selecting_llm(self, llm):
        from linhai.base import SystemMessage

        system_message = self.registry.get_member_typechecked(
            "system_message", SystemMessage
        )

        has_tool_use = any(
            t == "TOOL USE" for t, _ in system_message.introduction_items
        )
        has_waiting_user = any(
            t == "WAITING USER AND AUTO RUN"
            for t, _ in system_message.introduction_items
        )

        if llm.get_custom_toolcall_format():
            if not has_tool_use:
                from linhai.prompt import INTRODUCTION_TOOL_USE

                system_message.add_introduction("TOOL USE", INTRODUCTION_TOOL_USE)
            if not has_waiting_user:
                from linhai.prompt import INTRODUCTION_WAITING_USER

                system_message.add_introduction(
                    "WAITING USER AND AUTO RUN", INTRODUCTION_WAITING_USER
                )
        else:
            if has_tool_use:
                system_message.remove_introduction("TOOL USE")
            if has_waiting_user:
                system_message.remove_introduction("WAITING USER AND AUTO RUN")

    def register(self, lifecycle):
        lifecycle.after_selecting_llm.register(self.after_selecting_llm)
