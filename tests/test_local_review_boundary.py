"""The local review service must keep its HTTP traffic local and bounded."""

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hermes_fetch_ai import local_review


@pytest.mark.parametrize("url", ["http://[invalid]/v1", "http://user:pass@localhost/v1"])
def test_invalid_model_urls_are_rejected_without_raising(url):
    assert local_review.on_this_machine(url) is False


@pytest.mark.parametrize("timeout", ["nan", "inf", "0", "-1"])
def test_timeout_must_be_positive_and_finite(timeout, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"request": "x"})))
    assert local_review.main(["--timeout", timeout]) == 2
    assert "timeout" in capsys.readouterr().err


def test_model_redirect_is_not_followed():
    reached = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(302)
            self.send_header("Location", "/redirected")
            self.end_headers()

        def do_GET(self):
            reached.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"choices": [{"message": {"content": "answer"}}]}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(OSError):
            local_review.review("private code", f"http://127.0.0.1:{server.server_port}", "x", 2)
        assert not reached
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_oversized_model_answer_is_refused(monkeypatch):
    monkeypatch.setattr(local_review, "MAX_RESPONSE_BYTES", 128)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x" * 256)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError, match="too large"):
            local_review.review("private code", f"http://127.0.0.1:{server.server_port}", "x", 2)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("data", ["{", "[]", '{"request": 1}'])
def test_malformed_input_is_a_settings_error(data, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(data))
    assert local_review.main([]) == 2
    assert "JSON object" in capsys.readouterr().err
