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
