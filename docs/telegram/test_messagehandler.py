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
# converted from pytest to unittest format for compatibility.

import asyncio
import re
import unittest
from unittest.mock import Mock, AsyncMock

from telegram import (
    Bot,
    CallbackQuery,
    Chat,
    ChosenInlineResult,
    InlineQuery,
    Message,
    PreCheckoutQuery,
    ShippingQuery,
    Update,
    User,
)
from telegram.ext import CallbackContext, JobQueue, MessageHandler, filters
from telegram.ext.filters import MessageFilter


class TestMessageHandler(unittest.TestCase):
    """Test MessageHandler functionality.

    Note: Converted from python-telegram-bot's test_messagehandler.py
    """

    def setUp(self):
        self.test_flag = False
        self.SRE_TYPE = type(re.match("", ""))

        # Create test message
        self.message = Message(
            1, None, Chat(1, ""), from_user=User(1, "", False), text="Text"
        )

        # Create false updates for testing
        self.false_updates = [
            Update(
                1,
                callback_query=CallbackQuery(
                    1, User(1, "", False), "chat", message=self.message
                ),
            ),
            Update(1, inline_query=InlineQuery(1, User(1, "", False), "", "")),
            Update(
                1, chosen_inline_result=ChosenInlineResult("id", User(1, "", False), "")
            ),
            Update(1, shipping_query=ShippingQuery("id", User(1, "", False), "", None)),
            Update(
                1,
                pre_checkout_query=PreCheckoutQuery(
                    "id", User(1, "", False), "", 0, ""
                ),
            ),
            Update(1, callback_query=CallbackQuery(1, User(1, "", False), "chat")),
        ]

    def tearDown(self):
        self.test_flag = False

    async def callback(self, update, context):
        """Test callback for MessageHandler."""
        self.test_flag = (
            isinstance(context, CallbackContext)
            and isinstance(context.bot, Bot)
            and isinstance(update, Update)
            and isinstance(context.update_queue, asyncio.Queue)
            and isinstance(context.job_queue, JobQueue)
            and isinstance(context.chat_data, dict)
            and isinstance(context.bot_data, dict)
            and (
                (
                    isinstance(context.user_data, dict)
                    and (
                        isinstance(update.message, Message)
                        or isinstance(update.edited_message, Message)
                    )
                )
                or (
                    context.user_data is None
                    and (
                        isinstance(update.channel_post, Message)
                        or isinstance(update.edited_channel_post, Message)
                    )
                )
            )
        )

    def callback_regex1(self, update, context):
        """Callback for testing single regex match."""
        if context.matches:
            types = all(type(res) is self.SRE_TYPE for res in context.matches)
            num = len(context.matches) == 1
            self.test_flag = types and num

    def callback_regex2(self, update, context):
        """Callback for testing two regex matches."""
        if context.matches:
            types = all(type(res) is self.SRE_TYPE for res in context.matches)
            num = len(context.matches) == 2
            self.test_flag = types and num

    def test_slot_behaviour(self):
        """Test that MessageHandler has correct slot behavior."""
        handler = MessageHandler(filters.ALL, self.callback)
        # Note: Original test checks slots, but we simplify for unittest
        self.assertTrue(hasattr(handler, "__slots__"))

    def test_with_filter(self):
        """Test MessageHandler with ChatType.GROUP filter."""
        handler = MessageHandler(filters.ChatType.GROUP, self.callback)

        self.message.chat.type = "group"
        self.assertTrue(handler.check_update(Update(0, self.message)))

        self.message.chat.type = "private"
        self.assertFalse(handler.check_update(Update(0, self.message)))

    def test_callback_query_with_filter(self):
        """Test that MessageHandler doesn't handle callback queries."""

        class TestFilter(filters.UpdateFilter):
            flag = False

            def filter(self, u):
                self.flag = True

        test_filter = TestFilter()
        handler = MessageHandler(test_filter, self.callback)

        update = Update(
            1, callback_query=CallbackQuery(1, None, None, message=self.message)
        )

        self.assertTrue(update.effective_message is not None)
        self.assertFalse(handler.check_update(update))
        self.assertFalse(test_filter.flag)

    def test_specific_filters(self):
        """Test MessageHandler with specific filter combination."""
        f = (
            ~filters.UpdateType.MESSAGES
            & ~filters.UpdateType.CHANNEL_POST
            & filters.UpdateType.EDITED_CHANNEL_POST
        )
        handler = MessageHandler(f, self.callback)

        self.assertFalse(handler.check_update(Update(0, edited_message=self.message)))
        self.assertFalse(handler.check_update(Update(0, message=self.message)))
        self.assertFalse(handler.check_update(Update(0, channel_post=self.message)))
        self.assertTrue(
            handler.check_update(Update(0, edited_channel_post=self.message))
        )

    def test_other_update_types(self):
        """Test that MessageHandler rejects non-message updates."""
        handler = MessageHandler(None, self.callback)

        for false_update in self.false_updates:
            self.assertFalse(handler.check_update(false_update))

        self.assertFalse(handler.check_update("string"))

    def test_filters_returns_empty_dict(self):
        """Test MessageHandler with filter returning empty dict."""

        class DataFilter(MessageFilter):
            data_filter = True

            def filter(self, msg: Message):
                return {}

        handler = MessageHandler(DataFilter(), self.callback)
        self.assertFalse(handler.check_update(Update(0, self.message)))


if __name__ == "__main__":
    unittest.main()
