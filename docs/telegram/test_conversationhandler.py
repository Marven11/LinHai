#!/usr/bin/env python
#
# LinHai - A highly capable AI agent for complex tasks
# Copyright (C) 2024-2026 Marven11 and contributors
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
#
# WARNING: This project uses unittest, not pytest. The tests have been
# converted from python-telegram-bot's test_conversationhandler.py to unittest format for compatibility.

import unittest
from unittest.mock import Mock

from telegram import Update, Message, Chat, User, CallbackQuery
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, filters


class TestConversationHandler(unittest.TestCase):
    """Test ConversationHandler functionality."""

    def setUp(self):
        self.test_flag = False
        self.current_state = {}

        self.user1 = User(123, "TestUser", False)
        self.chat = Chat(0, Chat.GROUP)

        self.END = ConversationHandler.END
        self.THIRSTY, self.BREWING, self.DRINKING, self.CODING = range(4)

        self.entry_points = [CommandHandler("start", self.start_callback)]

        self.states = {
            self.THIRSTY: [
                CommandHandler("brew", self.brew_callback),
                CommandHandler("wait", self.start_callback),
            ],
            self.BREWING: [CommandHandler("pourCoffee", self.drink_callback)],
            self.DRINKING: [
                CommandHandler("startCoding", self.code_callback),
                CommandHandler("drinkMore", self.drink_callback),
                CommandHandler("end", self.end_callback),
            ],
            self.CODING: [
                CommandHandler("keepCoding", self.code_callback),
                CommandHandler("gettingThirsty", self.start_callback),
                CommandHandler("drinkMore", self.drink_callback),
            ],
        }

        self.fallbacks = [CommandHandler("eat", self.start_callback)]

    def start_callback(self, update, context):
        self.current_state[update.effective_user.id] = self.THIRSTY
        return self.THIRSTY

    def brew_callback(self, update, context):
        self.current_state[update.effective_user.id] = self.BREWING
        return self.BREWING

    def drink_callback(self, update, context):
        self.current_state[update.effective_user.id] = self.DRINKING
        return self.DRINKING

    def code_callback(self, update, context):
        self.current_state[update.effective_user.id] = self.CODING
        return self.CODING

    def end_callback(self, update, context):
        self.current_state[update.effective_user.id] = self.END
        return self.END

    def test_conversation_handler_creation(self):
        """Test that ConversationHandler can be created."""
        handler = ConversationHandler(
            entry_points=self.entry_points,
            states=self.states,
            fallbacks=self.fallbacks,
            name="test_conversation",
        )
        self.assertIsInstance(handler, ConversationHandler)
        self.assertEqual(handler.name, "test_conversation")

    def test_conversation_states(self):
        """Test conversation states structure."""
        handler = ConversationHandler(
            entry_points=self.entry_points, states=self.states, fallbacks=self.fallbacks
        )

        expected_states = {self.THIRSTY, self.BREWING, self.DRINKING, self.CODING}
        actual_states = set(handler.states.keys())
        self.assertEqual(actual_states, expected_states)

    def test_entry_points(self):
        """Test entry points configuration."""
        handler = ConversationHandler(
            entry_points=self.entry_points, states=self.states, fallbacks=self.fallbacks
        )

        self.assertEqual(len(handler.entry_points), 1)
        entry_handler = handler.entry_points[0]
        self.assertIsInstance(entry_handler, CommandHandler)
        self.assertEqual(entry_handler.commands, ["start"])

    def test_fallbacks(self):
        """Test fallbacks configuration."""
        handler = ConversationHandler(
            entry_points=self.entry_points, states=self.states, fallbacks=self.fallbacks
        )

        self.assertEqual(len(handler.fallbacks), 1)
        fallback_handler = handler.fallbacks[0]
        self.assertIsInstance(fallback_handler, CommandHandler)
        self.assertEqual(fallback_handler.commands, ["eat"])

    def test_per_chat_per_user_defaults(self):
        """Test default per_chat and per_user settings."""
        handler = ConversationHandler(
            entry_points=self.entry_points, states=self.states, fallbacks=self.fallbacks
        )

        self.assertTrue(handler.per_chat)
        self.assertTrue(handler.per_user)

    def test_conversation_timeout_setting(self):
        """Test conversation_timeout setting."""
        handler = ConversationHandler(
            entry_points=self.entry_points,
            states=self.states,
            fallbacks=self.fallbacks,
            conversation_timeout=30.0,
        )

        self.assertEqual(handler.conversation_timeout, 30.0)

    def test_map_to_parent_setting(self):
        """Test map_to_parent setting for nested conversations."""
        map_to_parent = {self.THIRSTY: self.BREWING, self.END: self.CODING}

        handler = ConversationHandler(
            entry_points=self.entry_points,
            states=self.states,
            fallbacks=self.fallbacks,
            map_to_parent=map_to_parent,
        )

        self.assertEqual(handler.map_to_parent, map_to_parent)

    def test_allow_reentry_setting(self):
        """Test allow_reentry setting."""
        handler = ConversationHandler(
            entry_points=self.entry_points,
            states=self.states,
            fallbacks=self.fallbacks,
            allow_reentry=True,
        )

        self.assertTrue(handler.allow_reentry)


if __name__ == "__main__":
    unittest.main()
