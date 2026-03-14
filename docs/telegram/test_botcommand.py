#!/usr/bin/env python
#
# A library that provides a Python interface to the Telegram Bot API
# Copyright (C) 2015-2026
# Leandro Toledo de Souza <devs@python-telegram-bot.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser Public License for more details.
#
# You should have received a copy of the GNU Lesser Public License
# along with this program.  If not, see [http://www.gnu.org/licenses/].

# 注意：本项目不使用pytest，以下测试代码已从pytest格式转换为unittest格式
# 请使用unittest模块运行测试，而不是pytest

import unittest
from unittest.mock import Mock

from telegram import BotCommand, Dice
from tests.auxil.slots import mro_slots


class TestBotCommandWithoutRequest(unittest.TestCase):
    command = "start"
    description = "A command"

    def setUp(self):
        self.bot_command = BotCommand(command="start", description="A command")
        self.offline_bot = Mock()

    def test_slot_behaviour(self):
        for attr in self.bot_command.__slots__:
            self.assertNotEqual(
                getattr(self.bot_command, attr, "err"),
                "err",
                f"got extra slot '{attr}'",
            )
        self.assertEqual(
            len(mro_slots(self.bot_command)),
            len(set(mro_slots(self.bot_command))),
            "duplicate slot",
        )

    def test_de_json(self):
        json_dict = {"command": self.command, "description": self.description}
        bot_command = BotCommand.de_json(json_dict, self.offline_bot)
        self.assertEqual(bot_command.api_kwargs, {})
        self.assertEqual(bot_command.command, self.command)
        self.assertEqual(bot_command.description, self.description)

    def test_to_dict(self):
        bot_command_dict = self.bot_command.to_dict()
        self.assertIsInstance(bot_command_dict, dict)
        self.assertEqual(bot_command_dict["command"], self.bot_command.command)
        self.assertEqual(bot_command_dict["description"], self.bot_command.description)

    def test_equality(self):
        a = BotCommand("start", "some description")
        b = BotCommand("start", "some description")
        c = BotCommand("start", "some other description")
        d = BotCommand("hepl", "some description")
        e = Dice(4, "emoji")

        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

        self.assertNotEqual(a, c)
        self.assertNotEqual(hash(a), hash(c))

        self.assertNotEqual(a, d)
        self.assertNotEqual(hash(a), hash(d))

        self.assertNotEqual(a, e)
        self.assertNotEqual(hash(a), hash(e))


if __name__ == "__main__":
    unittest.main()
