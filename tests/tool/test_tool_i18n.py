import importlib
import unittest
from unittest.mock import patch


def _reload_general():
    import linhai.tool.general as mod

    importlib.reload(mod)
    return mod.utils_tools


def _reload_mcp_connector():
    import linhai.tool.mcp_connector as mod
    import linhai.registry

    importlib.reload(mod)
    registry = linhai.registry.Registry()
    return mod.MCPConnector(registry)


class TestGeneralToolI18n(unittest.TestCase):
    @patch("linhai.utils.i18n.locale.getlocale")
    def test_fetch_webpage_desc_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        tools = _reload_general().tools
        self.assertIn("网页", tools["fetch_webpage"]["desc"])

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_fetch_webpage_desc_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        tools = _reload_general().tools
        self.assertIn("Fetch", tools["fetch_webpage"]["desc"])

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_search_web_desc_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        tools = _reload_general().tools
        self.assertIn("搜索", tools["search_web"]["desc"])

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_search_web_desc_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        tools = _reload_general().tools
        self.assertIn("Search", tools["search_web"]["desc"])

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_quickjs_calculator_desc_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        tools = _reload_general().tools
        self.assertIn("计算", tools["quickjs_calculator"]["desc"])

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_quickjs_calculator_desc_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        tools = _reload_general().tools
        self.assertIn("expression", tools["quickjs_calculator"]["desc"])

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_all_arg_descs_not_empty(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        tools = _reload_general().tools
        for name, tool in tools.items():
            for arg_name, arg_info in tool["args"].items():
                self.assertTrue(
                    len(arg_info["desc"]) > 0, f"tool {name} arg {arg_name} desc empty"
                )


class TestMCPConnectorToolI18n(unittest.TestCase):
    @patch("linhai.utils.i18n.locale.getlocale")
    def test_connect_mcp_server_desc_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        connector = _reload_mcp_connector()
        self.assertIn(
            "连接", connector.connector_toolset.tools["connect_mcp_server"]["desc"]
        )

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_connect_mcp_server_desc_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        connector = _reload_mcp_connector()
        self.assertIn(
            "Connect", connector.connector_toolset.tools["connect_mcp_server"]["desc"]
        )

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_disconnect_mcp_server_desc_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        connector = _reload_mcp_connector()
        self.assertIn(
            "断开", connector.connector_toolset.tools["disconnect_mcp_server"]["desc"]
        )

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_disconnect_mcp_server_desc_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        connector = _reload_mcp_connector()
        self.assertIn(
            "Disconnect",
            connector.connector_toolset.tools["disconnect_mcp_server"]["desc"],
        )

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_list_mcp_servers_desc_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        connector = _reload_mcp_connector()
        self.assertIn(
            "列出", connector.connector_toolset.tools["list_mcp_servers"]["desc"]
        )

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_list_mcp_servers_desc_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        connector = _reload_mcp_connector()
        self.assertIn(
            "List", connector.connector_toolset.tools["list_mcp_servers"]["desc"]
        )


if __name__ == "__main__":
    unittest.main()
