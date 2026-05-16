from hermes_fetch_ai._redaction import redact_dict, redact_text, short_sender
from hermes_fetch_ai.audit import AuditWriter


def test_bearer_sk_pk_jwt_hex_base64_seed_redacted():
    jwt = "eyJabc.def.ghi"
    text = (
        "Bearer abcdefghijklmnop sk-abcdefghijklmnopqrstuvwxyz pk-abcdefghijklmnopqrstuvwxyz seed=abcdefghijklmnopqrstuvwxyzabcdef 0x"
        + "a" * 40
        + " "
        + jwt
    )
    out = redact_text(text)
    assert "abcdefghijklmnopqrstuvwxyz" not in out
    assert "Bearer abc" not in out
    assert "sk-" not in out
    assert "pk-" not in out
    assert "0xaaa" not in out
    assert "eyJabc" not in out


def test_sender_address_shortened():
    assert "…" in short_sender("agent1qabcdefghijklmnopqrstuvwxyz")


def test_audit_writer_shortens_sender_short_too(tmp_path):
    sender = "agent1qabcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmnopqrstuvwxyz"
    path = tmp_path / "a.jsonl"
    AuditWriter(path).write(sender_short=sender, protocol="mcp", msg_type="call_tool")
    text = path.read_text(encoding="utf-8")
    assert sender not in text
    assert "…" in text


def test_redact_dict_key_values():
    assert redact_dict({"api_key": "value", "nested": {"token": "x"}})["api_key"] == "[REDACTED]"
