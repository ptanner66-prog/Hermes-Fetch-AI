from hermes_fetch_ai import audit
from hermes_fetch_ai.audit import AuditWriter


def test_audit_log_rotates_and_keeps_a_bounded_history(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "MAX_AUDIT_BYTES", 200)
    writer = AuditWriter(tmp_path / "audit.jsonl")
    for i in range(60):
        writer.write(trace_id=f"t{i:03d}", decision="allow", tool="echo")

    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["audit.jsonl", *(f"audit.jsonl.{n}" for n in range(1, audit.KEEP_FILES + 1))]
    assert '"t059"' in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert all(p.stat().st_size < 2 * 200 for p in tmp_path.iterdir())


def test_audit_record_keeps_only_allowlisted_fields(tmp_path):
    writer = AuditWriter(tmp_path / "audit.jsonl")
    writer.write(tool="echo", decision="allow", args={"text": "raw"}, output="raw output")
    line = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert '"tool": "echo"' in line
    assert "raw" not in line
    assert writer.count() == 1
