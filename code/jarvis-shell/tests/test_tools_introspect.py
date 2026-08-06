import pytest

from jarvis.tools.registry import REGISTRY
import jarvis.tools.introspect  # ensures it is registered


def test_tool_list_registered():
    assert "tool_list" in REGISTRY
    assert REGISTRY["tool_list"].risk == "low"
    assert REGISTRY["tool_list"].domain == "core"

def test_tool_list_output():
    result = jarvis.tools.introspect.tool_list()
    assert "tool_list (domain: core, risk: low)" in result
