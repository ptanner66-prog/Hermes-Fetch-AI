from hermes_fetch_ai.config import PolicyConfig
from hermes_fetch_ai.policy import (
    ReplayCache,
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


def test_global_call_rate_limit_blocks_sender_rotation():
    b = TokenBuckets()
    cfg = PolicyConfig(
        public_tools=["echo"],
        max_calls_per_minute_per_sender=10,
        max_global_calls_per_minute=2,
    )
    assert authorize("s1", "echo", {}, "mcp", cfg, b)[0]
    assert authorize("s2", "echo", {}, "mcp", cfg, b)[0]
    assert not authorize("s3", "echo", {}, "mcp", cfg, b)[0]


def test_sender_buckets_are_bounded_under_sybil_rotation():
    b = TokenBuckets()
    cfg = PolicyConfig(
        public_tools=["echo"],
        max_calls_per_minute_per_sender=10,
        max_global_calls_per_minute=100,
        max_tracked_senders=5,
    )
    for i in range(20):
        authorize(f"sender-{i}", "echo", {}, "mcp", cfg, b)
    assert len(b.hits) <= 5


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
    assert not authorize(
        "s", "ｅcho", {}, "mcp", PolicyConfig(public_tools=["echo"]), TokenBuckets()
    )[0]


def test_replay_cache_blocks_duplicates_and_bounds_entries():
    cache = ReplayCache()
    assert cache.allow("sender:req-1", ttl_seconds=60, max_entries=2)[0]
    ok, reason = cache.allow("sender:req-1", ttl_seconds=60, max_entries=2)
    assert not ok
    assert reason == "replay detected"

    for i in range(10):
        cache.allow(f"sender:req-{i + 2}", ttl_seconds=60, max_entries=2)
    assert len(cache.entries) <= 2
