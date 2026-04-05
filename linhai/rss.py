"""RSS模块，包含RSS消息定义、RSS解析工具函数和RSS定时检查插件。"""

import asyncio
import json
from typing import List, TYPE_CHECKING
import feedparser
import httpx

from linhai.llm import LanguageModelMessage, Message
from linhai.utils.common import UiNotice

if TYPE_CHECKING:
    from linhai.agent.main import Agent
    from linhai.agent import Agent as AgentType

from linhai.agent.state_machine import AgentStateMachine


class RssMessage(Message):
    """RSS消息，用于表示单个RSS条目。"""

    def __init__(self, title: str, link: str, pubdate: str, guid: str):
        self.title = title
        self.link = link
        self.pubdate = pubdate
        self.guid = guid

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        return (
            "<<rss>>\n"
            f"<<title>>{self.title}<<title>>\n"
            f"<<link>>{self.link}<<link>>\n"
            f"<<pubdate>>{self.pubdate}<<pubdate>>\n"
            f"<<guid>>{self.guid}<<guid>>\n"
            "<<rss>>"
        )

    def to_json(self) -> str:
        data = {
            "title": self.title,
            "link": self.link,
            "pubdate": self.pubdate,
            "guid": self.guid,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry):
        data = json.loads(json_str)
        return cls(
            title=data["title"],
            link=data["link"],
            pubdate=data["pubdate"],
            guid=data["guid"],
        )

    def __eq__(self, other) -> bool:
        """比较两个RssMessage是否相同。"""
        if not isinstance(other, RssMessage):
            return False
        return (
            self.title == other.title
            and self.link == other.link
            and self.pubdate == other.pubdate
            and self.guid == other.guid
        )

    def __hash__(self) -> int:
        """哈希支持，用于set比较。"""
        return hash((self.title, self.link, self.pubdate, self.guid))


def parse_rss(xml_content: str) -> List[RssMessage]:
    """解析RSS XML内容并返回RssMessage列表。

    Args:
        xml_content: RSS XML内容的字符串

    Returns:
        RssMessage列表，包含解析出的所有RSS条目

    Raises:
        ValueError: 当XML格式错误或无法解析时
    """
    feed = feedparser.parse(xml_content)

    if feed.bozo:
        raise ValueError(f"Failed to parse RSS XML: {feed.bozo_exception}")

    rss_messages: List[RssMessage] = []

    for entry in feed.entries:
        title_raw = entry.get("title", "")
        link_raw = entry.get("link", "")
        pubdate_raw = entry.get("published", "")
        guid_raw = entry.get("id", entry.get("guid", link_raw))

        title = str(title_raw) if title_raw else ""
        link = str(link_raw) if link_raw else ""
        pubdate = str(pubdate_raw) if pubdate_raw else ""
        guid = str(guid_raw) if guid_raw else link

        if not title:
            continue

        rss_messages.append(
            RssMessage(title=title, link=link, pubdate=pubdate, guid=guid)
        )

    return rss_messages


class RssPlugin:
    """RSS定时检查插件，定时轮询配置的RSS源并添加新消息到Agent消息队列。"""

    def __init__(self, registry, rss_urls, poll_interval):
        self.registry = registry
        self.rss_urls = rss_urls
        self.poll_interval = poll_interval
        self.processed_guids = set()

        self._initialized = False

    async def start_rss_polling(self):
        """启动RSS轮询任务。"""
        if not self.rss_urls:
            return

        while True:
            await self._poll_rss_sources()
            await asyncio.sleep(self.poll_interval)

    async def _poll_rss_sources(self):
        """轮询所有RSS源。"""
        from linhai.agent import Agent as AgentType

        agent = self.registry.get_member_typechecked("agent", AgentType)
        if not agent:
            return
        coros = await asyncio.gather(
            *[self._fetch_and_process_rss(rss_url, agent) for rss_url in self.rss_urls],
            return_exceptions=True,
        )
        for rss_url, result in zip(self.rss_urls, coros):
            if isinstance(result, Exception):
                await self.registry.send_if_exists(
                    "ui_log",
                    UiNotice(level="INFO", content=f"获取rss失败: {rss_url}"),
                )

    async def _fetch_and_process_rss(self, rss_url, agent, send_to_agent=True):
        """获取并处理单个RSS源。"""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(rss_url)
            if response.status_code != 200:
                return

            xml_content = response.text

        if feedparser.parse(xml_content).bozo:
            return

        rss_messages = parse_rss(xml_content)

        new_messages = [
            msg for msg in rss_messages if msg.guid not in self.processed_guids
        ]
        if not new_messages:
            return
        for msg in new_messages:
            self.processed_guids.add(msg.guid)
            if send_to_agent:
                await agent.message_processor.add_new_message(msg)
        if send_to_agent and new_messages:
            state_machine = self.registry.get_member_typechecked(
                "state_machine", AgentStateMachine
            )
            state_machine.interrupt_to_working()

    async def _initialize_processed_guids(self):
        """初始化时获取所有已存在的RSS消息的guid，不发送给agent。"""
        from linhai.agent import Agent as AgentType

        agent = self.registry.get_member_typechecked("agent", AgentType)
        if not agent:
            return

        for rss_url in self.rss_urls:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(rss_url)
                if response.status_code != 200:
                    continue
                xml_content = response.text

                if feedparser.parse(xml_content).bozo:
                    continue
                rss_messages = parse_rss(xml_content)
                for msg in rss_messages:
                    self.processed_guids.add(msg.guid)
        self._initialized = True

    async def before_agent_loop(self, agent: "Agent"):
        """在Agent循环开始前初始化RSS插件并启动轮询任务。"""
        if not self.rss_urls:
            return
        await self._initialize_processed_guids()
        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )
        task_supervisor.create_supervised_task("rss_polling", self.start_rss_polling)

    def register(self, lifecycle) -> None:
        """注册到Lifecycle。"""
        lifecycle.register_before_agent_loop(self.before_agent_loop)
