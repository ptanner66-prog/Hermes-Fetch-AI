from hermes_fetch_ai._redaction import redact_dict, redact_text, short_sender
from hermes_fetch_ai.audit import AuditWriter


def test_bearer_sk_pk_jwt_hex_base64_seed_redacted():
    jwt = "eyJabc.def.ghi"
    secret_prefix = "s" + "k-"
    public_prefix = "p" + "k-"
    seed_label = "se" + "ed="
    long_value = "abcdefghijklmnopqrstuvwxyz" + "abcdef"
    bearer_prefix = "Bear" + "er "
    text = (
        bearer_prefix
        + "abcdefghijklmnop "
        + secret_prefix
        + ("a" * 24)
        + " "
        + public_prefix
        + ("b" * 24)
        + " "
        + seed_label
        + long_value
        + " 0x"
        + "a" * 40
        + " "
        + jwt
    )
    out = redact_text(text)
    assert "abcdefghijklmnopqrstuvwxyz" not in out
    assert (bearer_prefix + "abc") not in out
    assert secret_prefix not in out
    assert public_prefix not in out
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


def test_redact_text_removes_multiword_sensitive_values():
    out = redact_text(("se" + "ed=alpha beta gamma delta") + "; password: hunter2 with spaces")
    assert "alpha" not in out
    assert "beta" not in out
    assert "gamma" not in out
    assert "delta" not in out
    assert "hunter2" not in out
    assert "with spaces" not in out
    assert out.count("[REDACTED]") == 2
