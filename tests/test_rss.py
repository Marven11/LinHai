import unittest
from linhai.agent.base import RssMessage


class TestRssMessage(unittest.TestCase):
    """RssMessage单元测试。"""

    def test_create_rss_message(self):
        """测试创建RssMessage对象。"""
        msg = RssMessage(
            title="Test Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        self.assertEqual(msg.title, "Test Title")
        self.assertEqual(msg.link, "http://example.com/article")
        self.assertEqual(msg.pubdate, "2026-03-21T10:00:00Z")
        self.assertEqual(msg.guid, "test-guid-123")

    def test_get_content(self):
        """测试get_content()方法。"""
        msg = RssMessage(
            title="Test Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        content = msg.get_content()
        self.assertIn("<<rss>>", content)
        self.assertIn("<<title>>Test Title<<title>>", content)
        self.assertIn("<<link>>http://example.com/article<<link>>", content)
        self.assertIn("<<pubdate>>2026-03-21T10:00:00Z<<pubdate>>", content)
        self.assertIn("<<guid>>test-guid-123<<guid>>", content)

    def test_eq(self):
        """测试__eq__()方法。"""
        msg1 = RssMessage(
            title="Test Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        msg2 = RssMessage(
            title="Test Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        msg3 = RssMessage(
            title="Different Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        self.assertEqual(msg1, msg2)
        self.assertNotEqual(msg1, msg3)
        self.assertNotEqual(msg1, "not a message")

    def test_hash(self):
        """测试__hash__()方法。"""
        msg1 = RssMessage(
            title="Test Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        msg2 = RssMessage(
            title="Test Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        msg3 = RssMessage(
            title="Different Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        self.assertEqual(hash(msg1), hash(msg2))
        self.assertNotEqual(hash(msg1), hash(msg3))
        # 可以用于set
        msg_set = {msg1, msg2, msg3}
        self.assertEqual(len(msg_set), 2)

    def test_to_json_from_json(self):
        """测试to_json()和from_json()方法。"""
        msg1 = RssMessage(
            title="Test Title",
            link="http://example.com/article",
            pubdate="2026-03-21T10:00:00Z",
            guid="test-guid-123",
        )
        json_str = msg1.to_json()
        msg2 = RssMessage.from_json(json_str, None)
        self.assertEqual(msg1, msg2)


if __name__ == "__main__":
    unittest.main()
