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
