import unittest
from pathlib import Path
from linhai.rss import RssMessage, parse_rss

TEST_RSS_FILE = Path(__file__).parent / "Marven11.rss"


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


class TestParseRss(unittest.TestCase):
    """parse_rss函数单元测试。"""

    def test_parse_rss_with_real_file(self):
        """测试使用真实的Marven11.rss文件解析。"""
        xml_content = TEST_RSS_FILE.read_text()
        messages = parse_rss(xml_content)
        self.assertGreater(len(messages), 0)
        self.assertEqual(
            messages[0].title,
            'Marven11 closed pull request <a href="http://localhost:3000/Marven11/LinHai/pulls/234">Marven11/LinHai#234</a>',
        )

    def test_parse_rss_atom(self):
        """测试解析Atom格式XML。"""
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Feed</title>
  <link href="http://example.com/"/>
  <updated>2003-12-13T18:30:02Z</updated>
  <entry>
    <title>Atom-Powered Robots Run Amok</title>
    <link href="http://example.com/2003/12/13/atom03"/>
    <id>urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a</id>
    <updated>2003-12-13T18:30:02Z</updated>
  </entry>
</feed>"""
        messages = parse_rss(xml_content)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].title, "Atom-Powered Robots Run Amok")
        self.assertEqual(messages[0].link, "http://example.com/2003/12/13/atom03")

    def test_parse_rss_missing_optional_fields(self):
        """测试缺失可选字段时的容错处理。"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Article Without Date</title>
      <link>http://example.com/article</link>
    </item>
  </channel>
</rss>"""
        messages = parse_rss(xml_content)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].title, "Article Without Date")
        self.assertEqual(messages[0].pubdate, "")

    def test_parse_rss_invalid_xml(self):
        """测试格式错误的XML处理。"""
        xml_content = "<invalid>xml</content>"
        with self.assertRaises(ValueError):
            parse_rss(xml_content)

    def test_parse_rss_empty_feed(self):
        """测试空RSS feed处理。"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
  </channel>
</rss>"""
        messages = parse_rss(xml_content)
        self.assertEqual(len(messages), 0)

    def test_parse_rss_missing_title(self):
        """测试缺失title的条目被跳过。"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <link>http://example.com/article</link>
    </item>
    <item>
      <title>Valid Article</title>
      <link>http://example.com/valid</link>
    </item>
  </channel>
</rss>"""
        messages = parse_rss(xml_content)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].title, "Valid Article")


if __name__ == "__main__":
    unittest.main()
