"""RSS模块，包含RSS消息定义和RSS解析工具函数。"""

import json
from typing import List
import feedparser

from linhai.llm import LanguageModelMessage, Message


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
    def from_json(cls, json_str: str, group_chat):
        data = json.loads(json_str)
        return cls(
            title=data["title"],
            link=data["link"],
            pubdate=data["pubdate"],
            guid=data["guid"],
        )

    def __eq__(self, other: object) -> bool:
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
