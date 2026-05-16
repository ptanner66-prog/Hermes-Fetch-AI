from types import SimpleNamespace

from hermes_fetch_ai.result_normalizer import from_call_tool_result, from_fastmcp_result


def test_from_call_tool_result_text_structured_error_binary_truncation():
    result = SimpleNamespace(
        content=[{"type": "text", "text": "hello"}, {"type": "image"}],
        structuredContent={"x": 1},
        isError=True,
    )
    out = from_call_tool_result(result, 10)
    assert out.structured == {"x": 1}
    assert out.is_error is True
    assert out.truncated is True
    assert "original_bytes" in out.text


def test_from_fastmcp_result_shapes():
    out = from_fastmcp_result({"answer": 3}, 100)
    assert out.structured == {"answer": 3}
    assert '"answer": 3' in out.text


def test_truncation_marker_includes_original_byte_count():
    out = from_fastmcp_result("abcdefghij", 8)
    assert out.truncated
    assert "original_bytes=10" in out.text
