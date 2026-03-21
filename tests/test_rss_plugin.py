import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.rss import RssPlugin, RssMessage, parse_rss


TEST_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Test Article 1</title>
      <link>http://example.com/article1</link>
      <pubDate>2026-03-21T10:00:00Z</pubDate>
      <guid>guid-1</guid>
    </item>
    <item>
      <title>Test Article 2</title>
      <link>http://example.com/article2</link>
      <pubDate>2026-03-21T10:00:01Z</pubDate>
      <guid>guid-2</guid>
    </item>
  </channel>
</rss>
"""


class TestRssPlugin(unittest.TestCase):
    """RssPlugin单元测试。"""

    def setUp(self):
        self.group_chat = Mock()
        self.group_chat.get_member_typechecked = Mock()
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.group_chat.get_member_typechecked.return_value = self.agent

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        plugin = RssPlugin(self.group_chat, ["http://example.com/feed"], 300)
        self.assertEqual(plugin.rss_urls, ["http://example.com/feed"])
        self.assertEqual(plugin.poll_interval, 300)
        self.assertEqual(len(plugin.processed_guids), 0)

    def test_plugin_with_empty_urls(self):
        """测试空RSS URL列表。"""
        plugin = RssPlugin(self.group_chat, [], 300)
        self.assertEqual(plugin.rss_urls, [])

    async def test_fetch_and_process_rss_success(self):
        """测试成功获取和处理RSS。"""
        plugin = RssPlugin(self.group_chat, ["http://example.com/feed"], 300)

        mock_response = Mock()
        mock_response.text = TEST_RSS_XML
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            await plugin._fetch_and_process_rss("http://example.com/feed", self.agent)

            self.assertEqual(self.agent.message_processor.add_new_message.call_count, 2)
            self.assertIn("guid-1", plugin.processed_guids)
            self.assertIn("guid-2", plugin.processed_guids)

    async def test_fetch_and_process_rss_duplicate(self):
        """测试RSS条目去重。"""
        plugin = RssPlugin(self.group_chat, ["http://example.com/feed"], 300)
        plugin.processed_guids.add("guid-1")

        mock_response = Mock()
        mock_response.text = TEST_RSS_XML
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            await plugin._fetch_and_process_rss("http://example.com/feed", self.agent)

            self.assertEqual(self.agent.message_processor.add_new_message.call_count, 1)
            self.assertIn("guid-1", plugin.processed_guids)
            self.assertIn("guid-2", plugin.processed_guids)

    async def test_fetch_and_process_rss_network_error(self):
        """测试网络错误处理。"""
        plugin = RssPlugin(self.group_chat, ["http://example.com/feed"], 300)

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.side_effect = Exception("Network error")
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            await plugin._fetch_and_process_rss("http://example.com/feed", self.agent)

            self.agent.message_processor.add_new_message.assert_not_called()

    async def test_fetch_and_process_rss_parse_error(self):
        """测试RSS解析错误处理。"""
        plugin = RssPlugin(self.group_chat, ["http://example.com/feed"], 300)

        mock_response = Mock()
        mock_response.text = "<invalid>xml</content>"
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            await plugin._fetch_and_process_rss("http://example.com/feed", self.agent)

            self.agent.message_processor.add_new_message.assert_not_called()

    async def test_before_agent_loop_with_urls(self):
        """测试Agent循环开始时启动轮询。"""
        plugin = RssPlugin(self.group_chat, ["http://example.com/feed"], 1)
        mock_agent = Mock()
        mock_lifecycle = Mock()

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = Mock()
            mock_create_task.return_value = mock_task

            await plugin.before_agent_loop(mock_agent)

            mock_create_task.assert_called_once()

    async def test_before_agent_loop_without_urls(self):
        """测试无RSS URL时不启动轮询。"""
        plugin = RssPlugin(self.group_chat, [], 300)
        mock_agent = Mock()

        with patch("asyncio.create_task") as mock_create_task:
            await plugin.before_agent_loop(mock_agent)

            mock_create_task.assert_not_called()

    def test_register(self):
        """测试注册到Lifecycle。"""
        plugin = RssPlugin(self.group_chat, ["http://example.com/feed"], 300)
        mock_lifecycle = Mock()

        plugin.register(mock_lifecycle)

        mock_lifecycle.register_before_agent_loop.assert_called_once_with(
            plugin.before_agent_loop
        )


if __name__ == "__main__":
    unittest.main()
