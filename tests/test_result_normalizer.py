from types import SimpleNamespace

from mcp.types import TextContent

from hermes_fetch_ai.result_normalizer import (
    error_result,
    from_call_tool_result,
    from_fastmcp_result,
)


def test_from_call_tool_result_text_error_binary_truncation():
    result = SimpleNamespace(
        content=[{"type": "text", "text": "hello"}, {"type": "image"}],
        structuredContent={"x": 1},
        isError=True,
    )
    out = from_call_tool_result(result, 10)
    assert out.is_error is True
    assert out.truncated is True
    assert out.output_bytes == len(b"hello\n[image content omitted]")
    assert len(out.text.encode("utf-8")) <= 10


def test_structured_content_is_used_when_there_is_no_text():
    result = SimpleNamespace(content=[], structuredContent={"answer": 3}, isError=False)
    assert from_call_tool_result(result, 100).text == '{"answer": 3}'


def test_empty_text_blocks_are_not_an_error():
    result = SimpleNamespace(content=[TextContent(type="text", text="")], isError=False)
    out = from_call_tool_result(result, 100)
    assert out.text == "" and out.is_error is False


def test_from_fastmcp_result_shapes():
    assert '"answer": 3' in from_fastmcp_result({"answer": 3}, 100).text
    assert from_fastmcp_result("plain", 100).text == "plain"
    blocks = [TextContent(type="text", text="a"), TextContent(type="text", text="b")]
    assert from_fastmcp_result(blocks, 100).text == "a\nb"
    # FastMCP returns (content, structured) for tools with structured output.
    assert from_fastmcp_result((blocks, {"result": "ab"}), 100).text == "a\nb"
    assert from_fastmcp_result(([], {"result": "ab"}), 100).text == '{"result": "ab"}'


def test_error_text_is_capped_like_output():
    out = error_result("x" * 500, 16)
    assert out.is_error and out.truncated
    assert len(out.text.encode("utf-8")) <= 16
    assert out.output_bytes == 500


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
