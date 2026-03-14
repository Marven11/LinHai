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
# converted from python-telegram-bot's test_filters.py to unittest format for compatibility.

import unittest
from unittest.mock import Mock
from datetime import datetime
import re

from telegram import (
    Chat,
    Message,
    MessageEntity,
    Update,
    User,
    Document,
    Sticker,
    File,
)
from telegram.ext import filters


class TestFilters(unittest.TestCase):
    """Test filters functionality.
    
    Note: Converted from python-telegram-bot's test_filters.py with simplifications.
    """
    
    def setUp(self):
        self.update = Update(
            0,
            Message(
                0,
                datetime.utcnow(),
                Chat(0, "private"),
                from_user=User(0, "Testuser", False),
            ),
        )
        self.update._unfreeze()
        self.update.message._unfreeze()
        self.update.message.chat._unfreeze()
        self.update.message.from_user._unfreeze()
    
    def test_filters_all(self):
        """Test that filters.ALL matches any update."""
        self.assertTrue(filters.ALL.check_update(self.update))
    
    def test_filters_text(self):
        """Test filters.TEXT and filters.Text."""
        self.update.message.text = "test"
        self.assertTrue(filters.TEXT.check_update(self.update))
        
        self.update.message.text = "/test"
        self.assertTrue(filters.Text().check_update(self.update))
        
        self.update.message.text = None
        self.assertFalse(filters.TEXT.check_update(self.update))
    
    def test_filters_text_strings(self):
        """Test filters.Text with specific strings."""
        self.update.message.text = "/test"
        self.assertTrue(filters.Text(("/test", "test1")).check_update(self.update))
        self.assertFalse(filters.Text(["test1", "test2"]).check_update(self.update))
    
    def test_filters_caption(self):
        """Test filters.CAPTION."""
        self.update.message.caption = "test"
        self.assertTrue(filters.CAPTION.check_update(self.update))
        
        self.update.message.caption = None
        self.assertFalse(filters.CAPTION.check_update(self.update))
    
    def test_filters_caption_strings(self):
        """Test filters.Caption with specific strings."""
        self.update.message.caption = "test"
        self.assertTrue(filters.Caption(("test", "test1")).check_update(self.update))
        self.assertFalse(filters.Caption(["test1", "test2"]).check_update(self.update))
    
    def test_filters_command_default(self):
        """Test filters.COMMAND with default behavior (command at beginning)."""
        self.update.message.text = "test"
        self.assertFalse(filters.COMMAND.check_update(self.update))
        
        self.update.message.text = "/test"
        self.update.message.entities = [MessageEntity(MessageEntity.BOT_COMMAND, 0, 5)]
        self.assertTrue(filters.COMMAND.check_update(self.update))
        
        # Command not at beginning
        self.update.message.entities = [MessageEntity(MessageEntity.BOT_COMMAND, 3, 5)]
        self.assertFalse(filters.COMMAND.check_update(self.update))
    
    def test_filters_command_anywhere(self):
        """Test filters.Command with anywhere=True."""
        self.update.message.entities = [MessageEntity(MessageEntity.BOT_COMMAND, 5, 4)]
        self.assertTrue(filters.Command(False).check_update(self.update))
    
    def test_filters_regex(self):
        """Test filters.Regex."""
        sre_type = type(re.match("", ""))
        
        self.update.message.text = "/start deep-linked param"
        result = filters.Regex(r"deep-linked param").check_update(self.update)
        self.assertTrue(result)
        self.assertIsInstance(result, dict)
        matches = result["matches"]
        self.assertIsInstance(matches, list)
        self.assertEqual(type(matches[0]), sre_type)
        
        self.update.message.text = "/help"
        self.assertTrue(filters.Regex(r"help").check_update(self.update))
        
        self.update.message.text = "test"
        self.assertFalse(filters.Regex(r"fail").check_update(self.update))
        self.assertTrue(filters.Regex(r"test").check_update(self.update))
        self.assertTrue(filters.Regex(re.compile(r"test")).check_update(self.update))
        self.assertTrue(filters.Regex(re.compile(r"TEST", re.IGNORECASE)).check_update(self.update))
        
        self.update.message.text = "i love python"
        self.assertTrue(filters.Regex(r".\b[lo]{2}ve python").check_update(self.update))
        
        self.update.message.text = None
        self.assertFalse(filters.Regex(r"fail").check_update(self.update))
    
    def test_filters_regex_multiple(self):
        """Test multiple regex filters combined."""
        sre_type = type(re.match("", ""))
        
        self.update.message.text = "/start deep-linked param"
        and_filter = filters.Regex("deep") & filters.Regex(r"linked param")
        result = and_filter.check_update(self.update)
        self.assertTrue(result)
        self.assertIsInstance(result, dict)
        matches = result["matches"]
        self.assertIsInstance(matches, list)
        self.assertTrue(all(type(res) is sre_type for res in matches))
        
        or_filter = filters.Regex("deep") | filters.Regex(r"linked param")
        result = or_filter.check_update(self.update)
        self.assertTrue(result)
        self.assertIsInstance(result, dict)
        matches = result["matches"]
        self.assertIsInstance(matches, list)
        self.assertTrue(all(type(res) is sre_type for res in matches))
    
    def test_filters_document_mime_type(self):
        """Test filters.Document with MIME types."""
        self.update.message.document = Document(
            "file_id", "unique_id", mime_type="application/vnd.android.package-archive"
        )
        self.update.message.document._unfreeze()
        
        self.assertTrue(filters.Document.APK.check_update(self.update))
        self.assertTrue(filters.Document.APPLICATION.check_update(self.update))
        self.assertFalse(filters.Document.DOC.check_update(self.update))
        self.assertFalse(filters.Document.AUDIO.check_update(self.update))
        
        self.update.message.document.mime_type = "application/msword"
        self.assertTrue(filters.Document.DOC.check_update(self.update))
        self.assertTrue(filters.Document.APPLICATION.check_update(self.update))
        self.assertFalse(filters.Document.DOCX.check_update(self.update))
        
        self.update.message.document.mime_type = "image/gif"
        self.assertTrue(filters.Document.GIF.check_update(self.update))
        self.assertTrue(filters.Document.IMAGE.check_update(self.update))
    
    def test_filters_sticker_types(self):
        """Test filters.Sticker for different sticker types."""
        self.update.message.sticker = Sticker("1", "uniq", 1, 2, False, False, Sticker.REGULAR)
        self.update.message.sticker._unfreeze()
        
        self.assertTrue(filters.Sticker.ALL.check_update(self.update))
        self.assertTrue(filters.Sticker.STATIC.check_update(self.update))
        self.assertFalse(filters.Sticker.VIDEO.check_update(self.update))
        self.assertFalse(filters.Sticker.PREMIUM.check_update(self.update))
        
        self.update.message.sticker.is_animated = True
        self.assertTrue(filters.Sticker.ANIMATED.check_update(self.update))
        self.assertFalse(filters.Sticker.STATIC.check_update(self.update))
        
        self.update.message.sticker.is_animated = False
        self.update.message.sticker.is_video = True
        self.assertTrue(filters.Sticker.VIDEO.check_update(self.update))
        self.assertFalse(filters.Sticker.ANIMATED.check_update(self.update))
    
    def test_filters_status_update(self):
        """Test filters.StatusUpdate."""
        self.assertFalse(filters.StatusUpdate.ALL.check_update(self.update))
        
        self.update.message.new_chat_members = ["test"]
        self.assertTrue(filters.StatusUpdate.ALL.check_update(self.update))
        self.assertTrue(filters.StatusUpdate.NEW_CHAT_MEMBERS.check_update(self.update))
        
        self.update.message.new_chat_members = None
        self.update.message.left_chat_member = "test"
        self.assertTrue(filters.StatusUpdate.ALL.check_update(self.update))
        self.assertTrue(filters.StatusUpdate.LEFT_CHAT_MEMBER.check_update(self.update))


if __name__ == '__main__':
    unittest.main()