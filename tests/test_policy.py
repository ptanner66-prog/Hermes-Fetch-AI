from hermes_fetch_ai.config import PolicyConfig
from hermes_fetch_ai.policy import (
    TokenBuckets,
    authorize,
    authorize_list_tools,
    normalize_tool_name,
    visible_tools,
)

TOOLS = [{"name": "echo"}, {"name": "add"}, {"name": "secret"}]


def test_empty_policy_denies_all_call_tool():
    ok, _ = authorize("s", "echo", {}, "mcp", PolicyConfig(), TokenBuckets())
    assert not ok


def test_visible_tools_filters_unknown_sender_to_public_or_empty():
    assert [t["name"] for t in visible_tools("s", TOOLS, PolicyConfig(public_tools=["echo"]))] == [
        "echo"
    ]
    assert visible_tools("s", TOOLS, PolicyConfig()) == []


def test_allowlisted_sender_sees_allowed_tools():
    out = visible_tools("s", TOOLS, PolicyConfig(allowed_senders={"s": ["add"]}))
    assert [t["name"] for t in out] == ["add"]


def test_denylist_beats_allowlist_public():
    cfg = PolicyConfig(
        public_tools=["echo"], allowed_senders={"s": ["secret"]}, denied_tools=["echo", "secret"]
    )
    assert visible_tools("s", TOOLS, cfg) == []
    assert not authorize("s", "echo", {}, "mcp", cfg, TokenBuckets())[0]


def test_call_rate_limit_blocks_above_threshold():
    b = TokenBuckets()
    cfg = PolicyConfig(public_tools=["echo"], max_calls_per_minute_per_sender=1)
    assert authorize("s", "echo", {}, "mcp", cfg, b)[0]
    assert not authorize("s", "echo", {}, "mcp", cfg, b)[0]


def test_list_rate_limit_blocks_above_threshold():
    b = TokenBuckets()
    cfg = PolicyConfig(public_tools=["echo"], max_list_tools_per_minute_per_sender=1)
    assert authorize_list_tools("s", cfg, b)[0]
    assert not authorize_list_tools("s", cfg, b)[0]


def test_tool_name_confusables_and_controls_rejected():
    for name in ["ｅcho", "echo\u200b", "echo\x1b[31m", "echo\n"]:
        try:
            normalize_tool_name(name)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"unsafe name accepted: {name!r}")
    assert not authorize("s", "ｅcho", {}, "mcp", PolicyConfig(public_tools=["echo"]), TokenBuckets())[0]
