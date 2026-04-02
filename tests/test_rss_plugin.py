import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.rss import RssPlugin, RssMessage, parse_rss
from linhai.task_supervisor import PlainTaskSupervisor


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
        self.registry = Mock()
        self.task_supervisor = Mock(spec=PlainTaskSupervisor)
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.add_new_message = AsyncMock()

        def get_member_typechecked_side_effect(name, cls):
            if name == "task_supervisor":
                return self.task_supervisor
            return self.agent

        self.registry.get_member_typechecked = Mock(
            side_effect=get_member_typechecked_side_effect
        )

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)
        self.assertEqual(plugin.rss_urls, ["http://example.com/feed"])
        self.assertEqual(plugin.poll_interval, 300)
        self.assertEqual(len(plugin.processed_guids), 0)

    def test_plugin_with_empty_urls(self):
        """测试空RSS URL列表。"""
        plugin = RssPlugin(self.registry, [], 300)
        self.assertEqual(plugin.rss_urls, [])

    def test_plugin_from_cli_args(self):
        """测试从TUI args获取RSS URL。"""
        import argparse

        mock_cli_args = argparse.Namespace()
        mock_cli_args.rss = ["http://example.com/feed", "http://example.com/feed2"]
        rss_urls = getattr(mock_cli_args, "rss", [])
        plugin = RssPlugin(self.registry, rss_urls, 300)
        self.assertEqual(
            plugin.rss_urls, ["http://example.com/feed", "http://example.com/feed2"]
        )
        self.assertEqual(plugin.poll_interval, 300)

    def test_fetch_and_process_rss_success(self):
        """测试成功获取和处理RSS。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)

        mock_response = Mock()
        mock_response.text = TEST_RSS_XML
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            asyncio.run(
                plugin._fetch_and_process_rss("http://example.com/feed", self.agent)
            )

            self.assertEqual(self.agent.message_processor.add_new_message.call_count, 2)
            self.assertIn("guid-1", plugin.processed_guids)
            self.assertIn("guid-2", plugin.processed_guids)

    def test_fetch_and_process_rss_duplicate(self):
        """测试RSS条目去重。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)
        plugin.processed_guids.add("guid-1")

        mock_response = Mock()
        mock_response.text = TEST_RSS_XML
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            asyncio.run(
                plugin._fetch_and_process_rss("http://example.com/feed", self.agent)
            )

            self.assertEqual(self.agent.message_processor.add_new_message.call_count, 1)
            self.assertIn("guid-1", plugin.processed_guids)
            self.assertIn("guid-2", plugin.processed_guids)

    def test_fetch_and_process_rss_network_error(self):
        """测试网络错误处理。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.side_effect = Exception("Network error")
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            with self.assertRaises(Exception) as context:
                asyncio.run(
                    plugin._fetch_and_process_rss("http://example.com/feed", self.agent)
                )

            self.assertIn("Network error", str(context.exception))
            self.agent.message_processor.add_new_message.assert_not_called()

    def test_fetch_and_process_rss_parse_error(self):
        """测试RSS解析错误处理。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)

        mock_response = Mock()
        mock_response.text = "<invalid>xml</content>"
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            asyncio.run(
                plugin._fetch_and_process_rss("http://example.com/feed", self.agent)
            )

            self.agent.message_processor.add_new_message.assert_not_called()

    def test_before_agent_loop_with_urls(self):
        """测试Agent循环开始时启动轮询。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 1)
        mock_agent = Mock()
        mock_lifecycle = Mock()

        with patch("linhai.rss.httpx.AsyncClient"):
            asyncio.run(plugin.before_agent_loop(mock_agent))

        self.task_supervisor.create_supervised_task.assert_called_once()

    def test_before_agent_loop_without_urls(self):
        """测试无RSS URL时不启动轮询。"""
        plugin = RssPlugin(self.registry, [], 300)
        mock_agent = Mock()

        asyncio.run(plugin.before_agent_loop(mock_agent))

        self.task_supervisor.create_supervised_task.assert_not_called()

    def test_fetch_and_process_rss_interrupts_agent(self):
        """测试RSS新消息会打断agent的sleeping状态。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)

        self.agent.state = "sleeping"
        self.agent.sleeping_since = "fake"
        self.agent.sleeping_deadline = "fake"
        self.agent.interrupt_to_working = Mock()

        mock_response = Mock()
        mock_response.text = TEST_RSS_XML
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            asyncio.run(
                plugin._fetch_and_process_rss("http://example.com/feed", self.agent)
            )

            self.agent.interrupt_to_working.assert_called_once()

    def test_fetch_and_process_rss_no_interrupt_without_new_messages(self):
        """测试无新RSS消息时不打断agent。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)
        plugin.processed_guids.add("guid-1")
        plugin.processed_guids.add("guid-2")

        self.agent.interrupt_to_working = Mock()

        mock_response = Mock()
        mock_response.text = TEST_RSS_XML
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            asyncio.run(
                plugin._fetch_and_process_rss("http://example.com/feed", self.agent)
            )

            self.agent.interrupt_to_working.assert_not_called()

    def test_fetch_and_process_rss_no_interrupt_when_not_sending(self):
        """测试send_to_agent=False时不打断agent。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)

        self.agent.interrupt_to_working = Mock()

        mock_response = Mock()
        mock_response.text = TEST_RSS_XML
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            asyncio.run(
                plugin._fetch_and_process_rss(
                    "http://example.com/feed", self.agent, send_to_agent=False
                )
            )

            self.agent.interrupt_to_working.assert_not_called()

    def test_register(self):
        """测试注册到Lifecycle。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)
        mock_lifecycle = Mock()

        plugin.register(mock_lifecycle)

        mock_lifecycle.register_before_agent_loop.assert_called_once_with(
            plugin.before_agent_loop
        )

    def test_poll_rss_sources(self):
        """测试轮询RSS源的功能。"""
        plugin = RssPlugin(self.registry, ["http://example.com/feed"], 300)

        mock_response = Mock()
        mock_response.text = TEST_RSS_XML
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch("linhai.rss.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_async_client

            asyncio.run(plugin._poll_rss_sources())

            self.assertEqual(self.agent.message_processor.add_new_message.call_count, 2)
            self.assertIn("guid-1", plugin.processed_guids)
            self.assertIn("guid-2", plugin.processed_guids)


if __name__ == "__main__":
    unittest.main()
