import json

import engram.main as main
from fastapi.testclient import TestClient


def _fake_run_agent(events):
    def _run(messages, client=None):
        yield from events
        messages.append({"role": "assistant", "content": "stub answer"})
    return _run


def _parse_sse(text):
    """Turn raw SSE text into a list of (event, data) tuples."""
    out = []
    for frame in text.strip().split("\n\n"):
        if not frame.strip():
            continue
        event, data = "message", ""
        for line in frame.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data += line[len("data:"):].strip()
        out.append((event, json.loads(data) if data else None))
    return out


def test_chat_emits_sse_start_token_done(monkeypatch):
    events = [
        {"type": "tool", "name": "search_code", "query": "loop", "status": "running"},
        {"type": "citations", "citations": [{"n": 1, "repo": "cativo23/engram",
            "path": "engram/agent.py", "line_start": 1, "line_end": 2,
            "similarity": 0.9, "snippet": "x", "github_url": "u"}]},
        {"type": "token", "text": "Hello "},
        {"type": "token", "text": "world"},
    ]
    monkeypatch.setattr(main, "run_agent", _fake_run_agent(events))
    client = TestClient(main.app)

    resp = client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse(resp.text)
    kinds = [e for e, _ in frames]
    assert kinds[0] == "start" and kinds[-1] == "done"
    assert "tool" in kinds and "citations" in kinds
    tokens = "".join(d["text"] for e, d in frames if e == "token")
    assert tokens == "Hello world"

    start_data = next(d for e, d in frames if e == "start")
    assert start_data["conversation_id"]


def test_chat_persists_conversation_for_followup(monkeypatch):
    monkeypatch.setattr(main, "run_agent",
                        _fake_run_agent([{"type": "token", "text": "ok"}]))
    client = TestClient(main.app)

    first = _parse_sse(client.post("/chat", json={"message": "one"}).text)
    conv_id = next(d for e, d in first if e == "start")["conversation_id"]

    # Same conversation id -> the stored message list keeps growing.
    client.post("/chat", json={"message": "two", "conversation_id": conv_id})
    assert conv_id in main.CONVERSATIONS
    user_turns = [m for m in main.CONVERSATIONS[conv_id]
                  if isinstance(m, dict) and m.get("role") == "user"]
    assert len(user_turns) == 2


def test_chat_error_path_emits_error_then_done_without_leaking(monkeypatch):
    def _boom(messages, client=None):
        yield {"type": "token", "text": "partial "}
        raise RuntimeError("kaboom-internal-detail")
    monkeypatch.setattr(main, "run_agent", _boom)
    client = TestClient(main.app)

    resp = client.post("/chat", json={"message": "hi"})
    frames = _parse_sse(resp.text)
    kinds = [e for e, _ in frames]
    assert "error" in kinds
    assert kinds[-1] == "done"  # done still fires last, even on error
    err = next(d for e, d in frames if e == "error")
    assert err["message"] == "recall failed; check server logs"
    assert "kaboom-internal-detail" not in resp.text  # no internal leak

    conv_id = next(d for e, d in frames if e == "start")["conversation_id"]
    assistant = [m for m in main.CONVERSATIONS[conv_id]
                 if isinstance(m, dict) and m.get("role") == "assistant"]
    assert assistant and assistant[-1]["content"] == "partial "  # partial answer persisted


def test_health_still_ok():
    client = TestClient(main.app)
    assert client.get("/health").json() == {"status": "ok"}
