from .message_checkers import Plugin

class MachineControlIntroductionPlugin(Plugin):

    async def before_message_generation(self, agent, history):
        machine_control = self.group_chat.get_members("machine_control")
        system_message = self.group_chat.get_members("system_message")
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
        lifecycle.register_before_message_generation(self.before_message_generation)