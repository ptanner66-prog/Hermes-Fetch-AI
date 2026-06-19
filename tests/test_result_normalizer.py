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
    assert out.output_bytes == len("hello\n[image content omitted]".encode("utf-8"))
    assert len(out.text.encode("utf-8")) <= 10


def test_from_fastmcp_result_shapes():
    out = from_fastmcp_result({"answer": 3}, 100)
    assert out.structured == {"answer": 3}
    assert '"answer": 3' in out.text


def test_truncation_marker_includes_original_byte_count_when_it_fits():
    out = from_fastmcp_result("abcdefghij" * 10, 64)
    assert out.truncated
    assert "original_bytes=100" in out.text
    assert len(out.text.encode("utf-8")) <= 64


def test_truncation_never_exceeds_max_bytes_when_marker_does_not_fit():
    out = from_fastmcp_result("x" * 100, 10)
    assert out.truncated
    assert out.output_bytes == 100
    assert len(out.text.encode("utf-8")) <= 10
