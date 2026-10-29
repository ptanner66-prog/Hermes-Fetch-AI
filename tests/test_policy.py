import pytest

from hermes_fetch_ai.config import PolicyConfig
from hermes_fetch_ai.policy import (
    PolicyState,
    ReplayCache,
    authorize,
    consume_call_rate,
    consume_list_tools_rate,
    replay_retention_seconds,
    visible_tools,
)
from hermes_fetch_ai.tool_names import MAX_TOOL_NAME_LENGTH, validate_tool_name

TOOLS = [{"name": "echo"}, {"name": "add"}, {"name": "secret"}]


def test_empty_policy_denies_all_call_tool():
    assert authorize("s", "echo", PolicyConfig()) == (False, "tool not allowed for sender")


def test_visible_tools_filters_unknown_sender_to_public_or_empty():
    assert [t["name"] for t in visible_tools("s", TOOLS, PolicyConfig(public_tools=["echo"]))] == [
        "echo"
    ]
    assert visible_tools("s", TOOLS, PolicyConfig()) == []


def test_allowlisted_sender_sees_allowed_tools():
    out = visible_tools("s", TOOLS, PolicyConfig(allowed_senders={"s": ["add"]}))
    assert [t["name"] for t in out] == ["add"]
    assert authorize("s", "add", PolicyConfig(allowed_senders={"s": ["add"]}))[0]


def test_denylist_beats_allowlist_public():
    cfg = PolicyConfig(
        public_tools=["echo"], allowed_senders={"s": ["secret"]}, denied_tools=["echo", "secret"]
    )
    assert visible_tools("s", TOOLS, cfg) == []
    assert authorize("s", "echo", cfg) == (False, "tool denied")


def test_backend_tools_with_unsafe_names_are_hidden():
    tools = [*TOOLS, {"name": "github/search"}, {"name": "\uff45cho"}]
    cfg = PolicyConfig(public_tools=["echo"])
    assert [t["name"] for t in visible_tools("s", tools, cfg)] == ["echo"]


def test_call_rate_limit_blocks_above_threshold():
    state = PolicyState()
    cfg = PolicyConfig(max_calls_per_minute_per_sender=1)
    assert consume_call_rate("s", cfg, state)[0]
    assert consume_call_rate("s", cfg, state) == (False, "rate limit exceeded")


def test_global_call_rate_limit_blocks_sender_rotation():
    state = PolicyState()
    cfg = PolicyConfig(max_calls_per_minute_per_sender=10, max_global_calls_per_minute=2)
    assert consume_call_rate("s1", cfg, state)[0]
    assert consume_call_rate("s2", cfg, state)[0]
    assert consume_call_rate("s3", cfg, state) == (False, "global rate limit exceeded")


def test_one_sender_over_its_limit_does_not_exhaust_the_global_budget():
    state = PolicyState()
    cfg = PolicyConfig(max_calls_per_minute_per_sender=30, max_global_calls_per_minute=300)
    results = [consume_call_rate("noisy", cfg, state)[0] for _ in range(300)]
    assert results.count(True) == 30
    assert consume_call_rate("someone-else", cfg, state) == (True, "allowed")


def test_zero_rate_limit_blocks_that_request_type():
    state = PolicyState()
    cfg = PolicyConfig(max_list_tools_per_minute_per_sender=0)
    assert consume_list_tools_rate("s", cfg, state) == (False, "rate limit exceeded")


def test_sender_buckets_are_bounded_under_sybil_rotation():
    state = PolicyState()
    cfg = PolicyConfig(
        max_calls_per_minute_per_sender=10, max_global_calls_per_minute=100, max_tracked_senders=5
    )
    for i in range(20):
        consume_call_rate(f"sender-{i}", cfg, state)
    assert len(state.buckets.hits) <= 5


def test_list_rate_limit_blocks_above_threshold():
    state = PolicyState()
    cfg = PolicyConfig(max_list_tools_per_minute_per_sender=1)
    assert consume_list_tools_rate("s", cfg, state)[0]
    assert not consume_list_tools_rate("s", cfg, state)[0]


@pytest.mark.parametrize(
    "name",
    ["\uff45cho", "echo\u200b", "echo\x1b[31m", "echo\n", "", "github/search", "web search"],
)
def test_unsafe_tool_names_are_rejected(name):
    with pytest.raises(ValueError, match="unsafe tool name"):
        validate_tool_name(name)


def test_tool_names_are_length_limited():
    assert validate_tool_name("a" * MAX_TOOL_NAME_LENGTH)
    with pytest.raises(ValueError, match="too long"):
        validate_tool_name("a" * (MAX_TOOL_NAME_LENGTH + 1))


def test_replay_cache_blocks_duplicates_and_bounds_entries():
    cache = ReplayCache()
    assert cache.remember("sender:req-1", retention_seconds=60, max_entries=2)[0]
    assert cache.remember("sender:req-1", retention_seconds=60, max_entries=2) == (
        False,
        "replay detected",
    )
    for i in range(10):
        cache.remember(f"sender:req-{i + 2}", retention_seconds=60, max_entries=2)
    assert len(cache.entries) <= 2


def test_replay_retention_covers_future_clock_skew():
    # A call stamped up to the allowed skew in the future stays fresh for
    # ttl + skew after it arrives, so its fingerprint must be kept that long.
    cfg = PolicyConfig(replay_ttl_seconds=300, max_replay_clock_skew_seconds=60)
    assert replay_retention_seconds(cfg) > 300 + 60
