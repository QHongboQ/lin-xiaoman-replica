"""戳一戳事件入口无视测试。

对应 issue #75：戳一戳不是对话消息，插件入口直接无视——
不缓存、不分析、不登记工作；不停事件，专门的戳一戳回应插件仍可处理。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
_PARENT = str(PLUGIN_ROOT.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

for _mod_path in (
    "astrbot",
    "astrbot.api",
    "astrbot.api.event",
    "astrbot.api.star",
    "astrbot.api.provider",
    "astrbot.core",
    "astrbot.core.agent",
    "astrbot.core.agent.message",
    "astrbot.core.message",
    "astrbot.core.message.components",
    "astrbot.core.star",
    "astrbot.core.star.context",
    "astrbot.core.star.register",
    "astrbot.core.star.star_tools",
    "astrbot.core.star.filter",
    "astrbot.core.star.filter.command",
    "astrbot.core.star.filter.command_group",
):
    sys.modules.setdefault(_mod_path, types.ModuleType(_mod_path))

sys.modules["astrbot.api"].logger = MagicMock()
sys.modules["astrbot.api.event"].MessageChain = MagicMock
sys.modules["astrbot.api.event"].AstrMessageEvent = type("AstrMessageEvent", (), {})
sys.modules["astrbot.core.star.context"].Context = type("Context", (), {})
sys.modules["astrbot.api.star"].Star = type(
    "Star", (), {"__init__": lambda self, ctx: None}
)
sys.modules["astrbot.api.star"].Context = type("Context", (), {})
sys.modules["astrbot.api.star"].register = lambda *a, **k: (lambda f: f)
sys.modules["astrbot.api.event"].filter = type(
    "Filter",
    (),
    {
        "EventMessageType": type(
            "EventMessageType",
            (),
            {"GROUP_MESSAGE": 1, "PRIVATE_MESSAGE": 2},
        ),
        "event_message_type": lambda *a, **k: (lambda f: f),
        "on_llm_request": lambda *a, **k: (lambda f: f),
        "on_decorating_result": lambda *a, **k: (lambda f: f),
        "after_message_sent": lambda *a, **k: (lambda f: f),
    },
)()
sys.modules["astrbot.api.provider"].ProviderRequest = type("ProviderRequest", (), {})
sys.modules["astrbot.api.provider"].LLMResponse = type("LLMResponse", (), {})
sys.modules["astrbot.core.star.register"].register_on_agent_done = lambda *a, **k: (
    lambda f: f
)
sys.modules["astrbot.core.star.star_tools"].StarTools = type(
    "StarTools", (), {"get_data_dir": staticmethod(lambda name: PLUGIN_ROOT)}
)
sys.modules["astrbot.core.star.filter.command"].CommandFilter = type(
    "CommandFilter", (), {}
)
sys.modules["astrbot.core.star.filter.command_group"].CommandGroupFilter = type(
    "CommandGroupFilter", (), {}
)

_components = sys.modules["astrbot.core.message.components"]


class _Plain:
    def __init__(self, text: str = ""):
        self.text = text


class _At:
    def __init__(self, qq: str = "", name: str = ""):
        self.qq = qq
        self.name = name


class _Poke:
    pass


_components.Plain = _Plain
_components.At = _At
_components.AtAll = type("AtAll", (), {})
_components.Reply = type("Reply", (), {})
_components.Poke = _Poke
_components.Image = type("Image", (), {})
_components.File = type("File", (), {})


class _FakeRuntimeTasks:
    async def run(self, event, fn):
        return await fn()


class _Event:
    """最小事件桩：消息链、大纲、extra 与停止标记。"""

    def __init__(self, chain=None, outline="", message_str="", is_at=False):
        self.unified_msg_origin = "aiocqhttp:GroupMessage:1108124091"
        self.message_str = message_str
        self.is_at_or_wake_command = is_at
        self._chain = chain or []
        self._outline = outline
        self._extras = {}
        self.stopped = False

    def get_messages(self):
        return self._chain

    def get_message_outline(self):
        return self._outline

    def get_sender_id(self):
        return "2172762770"

    def get_self_id(self):
        return "10000"

    def get_extra(self, key, default=None):
        return self._extras.get(key, default)

    def set_extra(self, key, value):
        self._extras[key] = value

    def stop_event(self):
        self.stopped = True

    def is_stopped(self):
        return self.stopped


def _plugin():
    from astrbot_plugin_angel_heart.main import AngelHeartPlugin

    plugin = object.__new__(AngelHeartPlugin)
    plugin._runtime_tasks = _FakeRuntimeTasks()
    plugin._is_upstream_command_event = MagicMock(return_value=False)
    plugin._is_blocked_by_provider_wake_prefix = MagicMock(return_value=False)
    plugin.config_manager = MagicMock()
    plugin.config_manager.whitelist_enabled = False
    return plugin


class TestPokeEntranceIgnore:
    def test_poke_event_ignored_and_not_stopped(self):
        plugin = _plugin()
        event = _Event(chain=[_Poke()], outline="[Poke]")
        assert plugin._should_process(event) is False
        assert event.stopped is False

    @pytest.mark.asyncio
    async def test_poke_never_reaches_front_desk(self):
        plugin = _plugin()
        plugin.front_desk = MagicMock()
        plugin.front_desk.handle_event = AsyncMock()
        event = _Event(chain=[_Poke()], outline="[Poke]")
        await plugin.smart_reply_handler(event)
        plugin.front_desk.handle_event.assert_not_awaited()
        assert event.stopped is False

    def test_plain_text_event_still_processed(self):
        plugin = _plugin()
        event = _Event(chain=[_Plain("你好")], outline="你好", message_str="你好")
        assert plugin._should_process(event) is True

    def test_at_self_event_still_processed(self):
        plugin = _plugin()
        event = _Event(
            chain=[_At(qq="10000")], outline="[At:10000]", message_str="", is_at=True
        )
        assert plugin._should_process(event) is True
