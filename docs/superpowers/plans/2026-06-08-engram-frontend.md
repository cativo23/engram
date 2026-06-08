# Engram Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the nightwire "recall console" web UI for Engram — a static HTML/CSS/JS page served by FastAPI — backed by an SSE-upgraded `/chat` that emits structured tool, citation, and token events.

**Architecture:** Phase 0 refactors the backend so `/chat` streams **Server-Sent Events** (`start` → `tool`/`citations` → `token`… → `done`) instead of plain text. The agent loop becomes a generator of typed event dicts; `search_code` returns structured hits (still a P1 stub) plus a formatter for the model's tool message. Phases 1–3 build the frontend: pure JS logic modules (SSE parsing + a state reducer) unit-tested with vitest, then the nightwire HTML/CSS productionized from the approved mockups, wired to the SSE stream, and mounted as static files in FastAPI.

**Tech Stack:** FastAPI + Starlette `StreamingResponse` (SSE), Python 3.14 + pytest, vanilla ES-module HTML/CSS/JS (no build to serve), vitest for JS logic tests, nightwire design tokens (vendored CSS).

**Design source of truth:** `docs/superpowers/specs/2026-06-08-engram-frontend-design.md`. Approved mockups: `.superpowers/brainstorm/131413-1780692909/content/{hybrid-hero,archive-console}.html`.

**SSE contract (the spine — every later task depends on this):**

```
event: start
data: {"conversation_id": "uuid"}

event: tool
data: {"name": "search_code", "query": "the agent loop", "status": "running"}

event: citations
data: {"citations": [{"n":1,"repo":"cativo23/llm-from-scratch","path":"02_agent.py","line_start":76,"line_end":102,"similarity":0.82,"snippet":"...","github_url":"https://github.com/cativo23/llm-from-scratch/blob/main/02_agent.py#L76-L102"}]}

event: token
data: {"text": "The agent loop "}

event: done
data: {}

event: error
data: {"message": "recall failed; check server logs"}
```

---

## File Structure

**Backend (modified):**
- `engram/tools.py` — `search_code` returns `list[dict]` structured hits; add `format_hits_for_model()`. `run_tool` returns the structured list.
- `engram/agent.py` — `run_agent(messages, client=None)` yields typed event dicts; OpenAI client injectable for tests; system prompt teaches `[n]` citations.
- `engram/main.py` — `/chat` emits SSE via an `sse()` frame helper; static UI mounted last.

**Backend (new):**
- `requirements-dev.txt` — pytest, httpx (FastAPI `TestClient` needs httpx).
- `tests/__init__.py`, `tests/test_tools.py`, `tests/test_agent.py`, `tests/test_chat_sse.py`.

**Frontend (new, under `engram/web/`):**
- `engram/web/sse.js` — pure `parseSSE()` + streaming `streamSSE()` wrapper.
- `engram/web/recall.js` — pure `initialState/reduce/fireRepos/lockSource`.
- `engram/web/render.js` — DOM updates from state (manual QA).
- `engram/web/app.js` — entry: health check, input wiring, fetch → stream → reduce → render.
- `engram/web/index.html` — hero + 3-zone console + command bar + footer.
- `engram/web/styles.css` — vendored nightwire tokens + ARCHIVE-mode layout.
- `engram/web/sse.test.js`, `engram/web/recall.test.js` — vitest logic tests.

**Tooling (new):**
- `package.json` — vitest devDependency + `test` script.
- `.gitignore` — add `node_modules/`.

---

## Task 1: Structured `search_code` stub + model formatter

**Files:**
- Modify: `engram/tools.py`
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Add the dev test dependencies**

Create `requirements-dev.txt`:

```text
# Dev/test dependencies (not needed to run the service).
pytest==8.3.4
httpx==0.28.1          # FastAPI TestClient transport
```

- [ ] **Step 2: Install them into the venv**

Run: `.venv/bin/pip install -r requirements-dev.txt`
Expected: `Successfully installed httpx-... pytest-...`

- [ ] **Step 3: Create the test package marker**

Create `tests/__init__.py` (empty file):

```python
```

- [ ] **Step 4: Write the failing test for structured hits + formatter**

Create `tests/test_tools.py`:

```python
from engram.tools import format_hits_for_model, run_tool, search_code


def test_search_code_returns_structured_hits():
    hits = search_code("the agent loop")
    assert isinstance(hits, list) and hits, "expected a non-empty list of hits"
    h = hits[0]
    for key in ("repo", "path", "line_start", "line_end", "similarity", "snippet", "github_url"):
        assert key in h, f"hit missing key: {key}"
    assert h["github_url"].startswith("https://github.com/")


def test_run_tool_dispatches_to_search_code():
    hits = run_tool("search_code", '{"query": "agent loop"}')
    assert isinstance(hits, list) and hits
    assert hits[0]["repo"]


def test_run_tool_unknown_returns_empty():
    assert run_tool("nope", "{}") == []


def test_format_numbers_hits_for_the_model():
    hits = [
        {"repo": "cativo23/x", "path": "a.py", "line_start": 1, "line_end": 9,
         "similarity": 0.91, "snippet": "code-a", "github_url": "u"},
        {"repo": "cativo23/y", "path": "b.py", "line_start": 3, "line_end": 4,
         "similarity": 0.50, "snippet": "code-b", "github_url": "u"},
    ]
    text = format_hits_for_model(hits)
    assert "[1] cativo23/x · a.py:1-9" in text
    assert "[2] cativo23/y · b.py:3-4" in text
    assert "code-a" in text and "code-b" in text


def test_format_respects_start_index():
    hits = [{"repo": "r", "path": "p", "line_start": 1, "line_end": 2,
             "similarity": 0.1, "snippet": "s", "github_url": "u"}]
    assert "[5] r · p:1-2" in format_hits_for_model(hits, start_index=5)


def test_format_empty_hits():
    assert format_hits_for_model([]) == "[no matches found]"
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tools.py -v`
Expected: FAIL — `ImportError: cannot import name 'format_hits_for_model'` (and/or `search_code` returns a str, not a list).

- [ ] **Step 6: Rewrite `engram/tools.py` to satisfy the tests**

Replace the entire contents of `engram/tools.py` with:

```python
"""Tools the agent can call.

`search_code` returns STRUCTURED hits (a list of dicts) so the API layer can emit
them as citation events, while `format_hits_for_model` turns them into the numbered
text the model reads (and cites with [n] markers). In P1 the hits are a STUB; P2
swaps the body for real pgvector similarity search — the return shape stays
identical, so nothing downstream changes.
"""

import json

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": (
                "Search the indexed code knowledge base for snippets relevant to a "
                "natural-language query. Returns matching code with repo/path/line "
                "citations. Use this for ANY question about the indexed code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "a focused, standalone search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


def search_code(query: str) -> list[dict]:
    """P1 STUB — returns placeholder STRUCTURED hits. Real vector search lands in P2.

    Each hit: repo, path, line_start, line_end, similarity, snippet, github_url.
    The shape is the contract the frontend renders; only the values become real in P2.
    """
    return [
        {
            "repo": "cativo23/llm-from-scratch",
            "path": "02_agent.py",
            "line_start": 76,
            "line_end": 102,
            "similarity": 0.82,
            "snippet": (
                "def take_turn(messages):\n"
                "    resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)\n"
                "    # run any requested tools, append results, then loop until no tool calls"
            ),
            "github_url": "https://github.com/cativo23/llm-from-scratch/blob/main/02_agent.py#L76-L102",
        },
        {
            "repo": "cativo23/engram",
            "path": "engram/agent.py",
            "line_start": 37,
            "line_end": 65,
            "similarity": 0.74,
            "snippet": (
                "def run_agent(messages, client=None):\n"
                "    # resolve tool calls (non-streamed), then stream the final answer"
            ),
            "github_url": "https://github.com/cativo23/engram/blob/main/engram/agent.py#L37-L65",
        },
    ]


def format_hits_for_model(hits: list[dict], start_index: int = 1) -> str:
    """Render hits as numbered text the model cites with [n] markers.

    `start_index` lets multiple search rounds keep one continuous [n] sequence.
    """
    if not hits:
        return "[no matches found]"
    blocks = []
    for i, h in enumerate(hits, start=start_index):
        blocks.append(
            f"[{i}] {h['repo']} · {h['path']}:{h['line_start']}-{h['line_end']} "
            f"(similarity {h['similarity']:.2f})\n{h['snippet']}"
        )
    return "\n\n".join(blocks)


TOOL_FUNCTIONS = {"search_code": search_code}


def run_tool(name: str, arguments: str) -> list[dict]:
    """Dispatch a tool call by name; return its STRUCTURED result (a list of hits)."""
    args = json.loads(arguments or "{}")
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return []
    return fn(**args)
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tools.py -v`
Expected: PASS (6 passed).

- [ ] **Step 8: Commit**

```bash
git add requirements-dev.txt tests/__init__.py tests/test_tools.py engram/tools.py
git commit -m "feat(tools): structured search_code hits + model formatter"
```

---

## Task 2: `run_agent` yields typed events

**Files:**
- Modify: `engram/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Write the failing test (fake client, no network)**

Create `tests/test_agent.py`:

```python
from types import SimpleNamespace

from engram.agent import run_agent


class FakeClient:
    """Returns scripted responses in order; ignores kwargs. Mimics the tiny slice
    of the OpenAI client run_agent uses: client.chat.completions.create(...)."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        return self._scripted.pop(0)


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=content, tool_calls=tool_calls))])


def _tool_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def _stream(*texts):
    return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=t))]) for t in texts]


def test_no_tool_path_yields_only_tokens():
    client = FakeClient([
        _msg(content="", tool_calls=None),          # round 1: model answers directly
        _stream("Hello ", "world"),                 # final streamed answer
    ])
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    events = list(run_agent(messages, client=client))
    assert [e["type"] for e in events] == ["token", "token"]
    assert "".join(e["text"] for e in events) == "Hello world"


def test_tool_path_emits_tool_then_citations_then_tokens():
    client = FakeClient([
        _msg(tool_calls=[_tool_call("search_code", '{"query": "agent loop"}')]),  # round 1: tool
        _msg(content="", tool_calls=None),                                        # round 2: ready
        _stream("The loop", " repeats[1]."),                                      # final answer
    ])
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
    events = list(run_agent(messages, client=client))
    types = [e["type"] for e in events]
    assert types == ["tool", "citations", "token", "token"]

    tool_ev = events[0]
    assert tool_ev["name"] == "search_code"
    assert tool_ev["query"] == "agent loop"
    assert tool_ev["status"] == "running"

    cites = events[1]["citations"]
    assert cites[0]["n"] == 1 and cites[1]["n"] == 2          # continuous numbering
    assert cites[0]["repo"] and "github_url" in cites[0]

    # The tool result text was appended to messages so the model could cite it.
    tool_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert tool_msgs and "[1]" in tool_msgs[0]["content"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_agent.py -v`
Expected: FAIL — `run_agent` currently doesn't accept `client=` and yields strings, not event dicts (`TypeError` or assertion failures).

- [ ] **Step 3: Rewrite `engram/agent.py` to emit typed events**

Replace the entire contents of `engram/agent.py` with:

```python
"""The agent loop, as a stream of typed events.

`run_agent` yields event dicts the API layer turns into Server-Sent Events:
  {"type": "tool",      "name": ..., "query": ..., "status": "running"}
  {"type": "citations", "citations": [<hit dicts, each with an "n" index>]}
  {"type": "token",     "text": ...}

Tool-resolution rounds run NON-streamed (so we can read tool_calls); the final
answer is STREAMED token-by-token. The OpenAI client is INJECTABLE so tests pass
a fake without touching the network.
"""

import json
from collections.abc import Iterator

from openai import OpenAI

from .config import settings
from .tools import TOOLS_SCHEMA, format_hits_for_model, run_tool

_default_client = OpenAI(
    base_url=settings.openrouter_base_url,
    api_key=settings.openrouter_api_key,
)

SYSTEM_PROMPT = (
    "You are Engram, an assistant that answers questions about a user's indexed "
    "code using the search_code tool. Always search before answering a question "
    "about the code. Ground every factual claim in the search results. The search "
    "results are numbered ([1], [2], ...); cite the ones you use with their bracket "
    "marker inline, e.g. 'the loop repeats[1].'. If search_code finds nothing "
    "relevant, say you couldn't find it — never invent code or answer from prior "
    "knowledge. Keep answers concise."
)


def system_message() -> dict:
    """The seed message that opens every conversation."""
    return {"role": "system", "content": SYSTEM_PROMPT}


def _extract_query(arguments: str) -> str:
    try:
        return json.loads(arguments or "{}").get("query", "")
    except (ValueError, AttributeError):
        return ""


def run_agent(messages: list, client: OpenAI | None = None) -> Iterator[dict]:
    """Yield typed events for one user turn; mutate `messages` with the trace.

    `messages` is mutated in place (tool requests + tool results appended) so the
    caller can persist the whole conversation as memory.
    """
    client = client or _default_client
    citation_count = 0

    # 1) Tool-resolution rounds (bounded) — non-streamed so we can read tool_calls.
    for _ in range(settings.max_tool_iterations):
        resp = client.chat.completions.create(
            model=settings.model, messages=messages, tools=TOOLS_SCHEMA,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            break  # the model is ready to answer
        messages.append(msg)
        for call in msg.tool_calls:
            args = call.function.arguments or "{}"
            yield {
                "type": "tool",
                "name": call.function.name,
                "query": _extract_query(args),
                "status": "running",
            }
            hits = run_tool(call.function.name, args)
            start = citation_count + 1
            numbered = [{**h, "n": citation_count + 1 + i} for i, h in enumerate(hits)]
            citation_count += len(hits)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": format_hits_for_model(hits, start_index=start),
            })
            if numbered:
                yield {"type": "citations", "citations": numbered}

    # 2) Final answer — streamed (no tools, so the model must produce text).
    stream = client.chat.completions.create(
        model=settings.model, messages=messages, stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield {"type": "token", "text": chunk.choices[0].delta.content}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_agent.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add engram/agent.py tests/test_agent.py
git commit -m "feat(agent): run_agent yields typed tool/citation/token events"
```

---

## Task 3: `/chat` streams Server-Sent Events

**Files:**
- Modify: `engram/main.py`
- Create: `tests/test_chat_sse.py`

> Note: the static UI mount is NOT added here — `engram/web/` doesn't exist yet and `StaticFiles` would raise at import. It is added in Task 8.

- [ ] **Step 1: Write the failing test (monkeypatch our own `run_agent`)**

Create `tests/test_chat_sse.py`:

```python
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


def test_health_still_ok():
    client = TestClient(main.app)
    assert client.get("/health").json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chat_sse.py -v`
Expected: FAIL — current `/chat` returns `text/plain` plain tokens, no `event:`/`data:` frames; `content-type` assertion and frame parsing fail.

- [ ] **Step 3: Rewrite `engram/main.py` for SSE**

Replace the entire contents of `engram/main.py` with:

```python
"""Engram API — a streaming /chat over Server-Sent Events.

Run:  uvicorn engram.main:app --reload
"""

import json
import logging
import uuid
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import run_agent, system_message

logger = logging.getLogger("engram")

app = FastAPI(
    title="Engram",
    description="Query your code with citation-backed answers.",
    version="0.1.0",
)

# P1: in-memory conversation store (single process). P2+ can move this to a DB.
CONVERSATIONS: dict[str, list] = {}


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None       # omit to start a new conversation


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/health")
def health() -> dict:
    """Liveness probe — drives the UI's ONLINE indicator."""
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """Stream the answer as SSE: start -> tool/citations -> token... -> done.

    The conversation id is sent in the `start` event; pass it back as
    `conversation_id` to continue the same conversation.
    """
    conv_id = req.conversation_id or str(uuid.uuid4())
    messages = CONVERSATIONS.setdefault(conv_id, [system_message()])
    messages.append({"role": "user", "content": req.message})

    def generate() -> Iterator[str]:
        yield sse("start", {"conversation_id": conv_id})
        answer: list[str] = []
        try:
            for ev in run_agent(messages):
                if ev["type"] == "token":
                    answer.append(ev["text"])
                    yield sse("token", {"text": ev["text"]})
                elif ev["type"] == "tool":
                    yield sse("tool", {"name": ev["name"], "query": ev["query"],
                                       "status": ev["status"]})
                elif ev["type"] == "citations":
                    yield sse("citations", {"citations": ev["citations"]})
        except Exception:
            logger.exception("run_agent failed")
            yield sse("error", {"message": "recall failed; check server logs"})
        finally:
            # Persist the assistant's reply (even if partial) so the next turn remembers it.
            messages.append({"role": "assistant", "content": "".join(answer)})
        yield sse("done", {})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_chat_sse.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the whole backend suite (no regressions)**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS (all of tools + agent + chat_sse tests green).

- [ ] **Step 6: Commit**

```bash
git add engram/main.py tests/test_chat_sse.py
git commit -m "feat(api): stream /chat as structured Server-Sent Events"
```

---

## Task 4: Frontend SSE parser (vitest)

**Files:**
- Create: `package.json`
- Modify: `.gitignore`
- Create: `engram/web/sse.js`
- Create: `engram/web/sse.test.js`

- [ ] **Step 1: Create `package.json` with vitest**

Create `package.json` at the repo root:

```json
{
  "name": "engram-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "description": "Static frontend logic tests for Engram (vitest). The served UI needs no build step.",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "vitest": "^2.1.8"
  }
}
```

- [ ] **Step 2: Ignore node_modules**

Add this line to `.gitignore`:

```text
node_modules/
```

- [ ] **Step 3: Install vitest**

Run: `npm install`
Expected: `added N packages` and a `node_modules/` directory appears.

- [ ] **Step 4: Write the failing SSE parser test**

Create `engram/web/sse.test.js`:

```javascript
import { describe, it, expect } from "vitest";
import { parseSSE } from "./sse.js";

describe("parseSSE", () => {
  it("parses complete frames and JSON-decodes data", () => {
    const text =
      'event: start\ndata: {"conversation_id":"abc"}\n\n' +
      'event: token\ndata: {"text":"hi"}\n\n';
    const { events, rest } = parseSSE(text, "");
    expect(rest).toBe("");
    expect(events).toEqual([
      { event: "start", data: { conversation_id: "abc" } },
      { event: "token", data: { text: "hi" } },
    ]);
  });

  it("holds back an incomplete trailing frame in `rest`", () => {
    const { events, rest } = parseSSE('event: token\ndata: {"text":"a"}\n\nevent: tok', "");
    expect(events).toHaveLength(1);
    expect(rest).toBe("event: tok");
  });

  it("stitches a frame split across two chunks via the buffer", () => {
    const first = parseSSE('event: token\nda', "");
    expect(first.events).toHaveLength(0);
    const second = parseSSE('ta: {"text":"x"}\n\n', first.rest);
    expect(second.events).toEqual([{ event: "token", data: { text: "x" } }]);
  });

  it("defaults event name to 'message' and tolerates bad JSON", () => {
    const { events } = parseSSE("data: not-json\n\n", "");
    expect(events).toEqual([{ event: "message", data: null }]);
  });
});
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `npm test`
Expected: FAIL — cannot resolve `./sse.js` (module does not exist yet).

- [ ] **Step 6: Implement `engram/web/sse.js`**

Create `engram/web/sse.js`:

```javascript
// Server-Sent Events parsing for the Engram recall console.
//
// `parseSSE` is PURE: given the leftover buffer plus a new chunk of text, it
// returns the complete events it could parse and the (possibly incomplete)
// trailing frame to carry into the next call. This is the unit-tested core.
//
// `streamSSE` is the thin runtime wrapper around a fetch() ReadableStream.

export function parseSSE(chunkText, buffer) {
  buffer += chunkText;
  const frames = buffer.split("\n\n");
  const rest = frames.pop(); // last element is the incomplete tail (or "")
  const events = [];
  for (const frame of frames) {
    if (!frame.trim()) continue;
    let event = "message";
    let data = "";
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    let parsed = null;
    try {
      parsed = data ? JSON.parse(data) : null;
    } catch {
      parsed = null;
    }
    events.push({ event, data: parsed });
  }
  return { events, rest };
}

// Async generator over a fetch Response body. Usage:
//   for await (const { event, data } of streamSSE(response)) { ... }
export async function* streamSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const { events, rest } = parseSSE(decoder.decode(value, { stream: true }), buffer);
    buffer = rest;
    for (const ev of events) yield ev;
  }
}
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `npm test`
Expected: PASS (4 passed).

- [ ] **Step 8: Commit**

```bash
git add package.json .gitignore engram/web/sse.js engram/web/sse.test.js
git commit -m "feat(web): SSE stream parser with vitest coverage"
```

---

## Task 5: Recall state reducer (vitest)

**Files:**
- Create: `engram/web/recall.js`
- Create: `engram/web/recall.test.js`

- [ ] **Step 1: Write the failing reducer test**

Create `engram/web/recall.test.js`:

```javascript
import { describe, it, expect } from "vitest";
import { initialState, reduce, fireRepos, lockSource } from "./recall.js";

const REPOS = [
  { name: "nightwire", lang: "CSS", chunks: 142 },
  { name: "llm-from-scratch", lang: "PY", chunks: 96 },
  { name: "engram", lang: "PY", chunks: 51 },
];

function apply(events) {
  return events.reduce(reduce, initialState(REPOS));
}

describe("fireRepos", () => {
  it("fires repos present in citations (matched by basename), max similarity wins", () => {
    const cites = [
      { repo: "cativo23/nightwire", similarity: 0.6 },
      { repo: "cativo23/nightwire", similarity: 0.88 },
      { repo: "cativo23/engram", similarity: 0.4 },
    ];
    const repos = fireRepos(REPOS.map(r => ({ ...r, fired: false, score: null })), cites);
    const byName = Object.fromEntries(repos.map(r => [r.name, r]));
    expect(byName["nightwire"].fired).toBe(true);
    expect(byName["nightwire"].score).toBeCloseTo(0.88);
    expect(byName["engram"].fired).toBe(true);
    expect(byName["llm-from-scratch"].fired).toBe(false);
    expect(byName["llm-from-scratch"].score).toBeNull();
  });
});

describe("reduce", () => {
  it("start resets answer/citations and clears fired repos", () => {
    const s = apply([
      { event: "citations", data: { citations: [{ n: 1, repo: "cativo23/nightwire", similarity: 0.8 }] } },
      { event: "token", data: { text: "old" } },
      { event: "start", data: { conversation_id: "c" } },
    ]);
    expect(s.answer).toBe("");
    expect(s.citations).toEqual([]);
    expect(s.repos.every(r => !r.fired)).toBe(true);
    expect(s.status).toBe("searching");
  });

  it("records the retrieval trace from tool events", () => {
    const s = apply([{ event: "tool", data: { name: "search_code", query: "loop" } }]);
    expect(s.trace).toEqual([{ name: "search_code", query: "loop" }]);
  });

  it("accumulates citations, fires repos, and locks onto the first citation", () => {
    const s = apply([
      { event: "citations", data: { citations: [
        { n: 1, repo: "cativo23/nightwire", path: "modes.css", similarity: 0.88 },
        { n: 2, repo: "cativo23/engram", path: "agent.py", similarity: 0.5 },
      ] } },
    ]);
    expect(s.citations).toHaveLength(2);
    expect(s.sourceLock.n).toBe(1);
    expect(s.repos.find(r => r.name === "nightwire").fired).toBe(true);
  });

  it("appends streamed tokens into the answer", () => {
    const s = apply([
      { event: "token", data: { text: "Hello " } },
      { event: "token", data: { text: "world" } },
    ]);
    expect(s.answer).toBe("Hello world");
    expect(s.status).toBe("streaming");
  });

  it("done sets terminal status", () => {
    const s = apply([{ event: "done", data: {} }]);
    expect(s.status).toBe("done");
  });
});

describe("lockSource", () => {
  it("locks SOURCE LOCK onto a citation by its [n]", () => {
    const base = apply([
      { event: "citations", data: { citations: [
        { n: 1, repo: "cativo23/nightwire", similarity: 0.88 },
        { n: 2, repo: "cativo23/engram", similarity: 0.5 },
      ] } },
    ]);
    expect(lockSource(base, 2).sourceLock.n).toBe(2);
    expect(lockSource(base, 99).sourceLock.n).toBe(1); // unknown n -> unchanged
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test`
Expected: FAIL — cannot resolve `./recall.js`.

- [ ] **Step 3: Implement `engram/web/recall.js`**

Create `engram/web/recall.js`:

```javascript
// Pure state reducers that turn the SSE event log into console view-state.
// No DOM here — this is the unit-tested brain of the recall console.

export function initialState(repos) {
  return {
    status: "standby", // standby | searching | streaming | done | error
    repos: repos.map((r) => ({ ...r, fired: false, score: null })),
    trace: [], // [{ name, query }]
    citations: [], // [{ n, repo, path, line_start, line_end, similarity, snippet, github_url }]
    answer: "",
    sourceLock: null,
    error: null,
  };
}

// A repo "fires" when it appears in the citations; its score is the max similarity
// of its hits. Citations carry "owner/name"; INDEX CORE lists bare names — match on basename.
export function fireRepos(repos, citations) {
  const best = {};
  for (const c of citations) {
    const name = c.repo.includes("/") ? c.repo.split("/").pop() : c.repo;
    best[name] = Math.max(best[name] ?? 0, c.similarity ?? 0);
  }
  return repos.map((r) =>
    r.name in best
      ? { ...r, fired: true, score: best[r.name] }
      : { ...r, fired: false, score: null }
  );
}

export function reduce(state, ev) {
  switch (ev.event) {
    case "start":
      return {
        ...state,
        status: "searching",
        answer: "",
        citations: [],
        trace: [],
        sourceLock: null,
        error: null,
        repos: state.repos.map((r) => ({ ...r, fired: false, score: null })),
      };
    case "tool":
      return {
        ...state,
        status: "searching",
        trace: [...state.trace, { name: ev.data.name, query: ev.data.query }],
      };
    case "citations": {
      const citations = [...state.citations, ...ev.data.citations];
      return {
        ...state,
        citations,
        repos: fireRepos(state.repos, citations),
        sourceLock: state.sourceLock || citations[0] || null,
      };
    }
    case "token":
      return { ...state, status: "streaming", answer: state.answer + ev.data.text };
    case "done":
      return { ...state, status: "done" };
    case "error":
      return { ...state, status: "error", error: ev.data?.message ?? "unknown error" };
    default:
      return state;
  }
}

// Click a [n] badge -> show that citation in SOURCE LOCK. Unknown n -> unchanged.
export function lockSource(state, n) {
  const c = state.citations.find((x) => x.n === n);
  return c ? { ...state, sourceLock: c } : state;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test`
Expected: PASS (all sse + recall tests green).

- [ ] **Step 5: Commit**

```bash
git add engram/web/recall.js engram/web/recall.test.js
git commit -m "feat(web): recall console state reducer with firing-repos logic"
```

---

## Task 6: HTML structure + nightwire styles (ARCHIVE mode)

**Files:**
- Create: `engram/web/index.html`
- Create: `engram/web/styles.css`

This task productionizes the approved mockups (`hybrid-hero.html` + `archive-console.html`) into real files. No JS wiring yet — the page renders the standby state with hard-coded placeholder content that Task 7 replaces with live data.

- [ ] **Step 1: Create `engram/web/styles.css`**

```css
/* Engram recall console — ARCHIVE intensity (fixed).
   Design tokens vendored from nightwire (github.com/cativo23/nightwire):
   pure-black surfaces, soft neon, tonal elevation (no shadows), 2px panel gaps. */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Noto+Serif+Display:wght@900&family=Saira+Extra+Condensed:wght@600&family=Shippori+Mincho+B1:wght@800&display=swap');

:root {
  --void: #000;
  --void-warm: #080808;
  --primary: #6699ff;      --primary-dim: #4477cc;
  --green: #7aed7a;        --green-dim: #5cb85c;
  --cyan: #66ddff;         --cyan-dim: #44aacc;
  --purple: #b266e0;       --purple-dim: #8844bb;
  --text: #e6e6e6;         --text-dim: #888;
  --faint: rgba(255, 255, 255, 0.05);
  --line: rgba(255, 255, 255, 0.10);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--void);
  color: var(--text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
  line-height: 1.5;
}

.stamp {
  font-family: 'Saira Extra Condensed', 'Impact', sans-serif;
  font-weight: 600; text-transform: uppercase; letter-spacing: .1em;
}
.title {
  font-family: 'Noto Serif Display', serif;
  font-weight: 900; text-transform: uppercase;
  transform: scaleX(.82); transform-origin: center; display: inline-block;
}

/* ---- HERO ---- */
.hero {
  min-height: 320px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; text-align: center;
  padding: 56px 20px 36px; border-bottom: 1px solid var(--faint);
}
.hero .kanji { font-family: 'Shippori Mincho B1', serif; color: var(--primary-dim); font-size: 18px; letter-spacing: .3em; }
.hero h1 { margin: 10px 0 0; }
.hero .sig { font-size: 62px; letter-spacing: .16em; color: var(--text); }
.hero .pitch { margin-top: 22px; max-width: 580px; color: var(--text-dim); font-size: 13px; line-height: 1.7; }
.hero .pitch b { color: var(--text); }
.diffs { display: flex; gap: 2px; margin-top: 28px; flex-wrap: wrap; justify-content: center; }
.diffs div { border: 1px solid var(--faint); padding: 8px 14px; font-size: 10px; color: var(--text-dim); }
.diffs b { color: var(--cyan-dim); }
.status { margin-top: 26px; font-size: 10px; color: #4a4a4a; }
.status .on { color: var(--green-dim); }
.status .off { color: var(--text-dim); }
.cta { margin-top: 22px; color: var(--primary-dim); font-size: 11px; text-decoration: none; }

/* ---- CONSOLE ---- */
.console-h {
  font-size: 10px; color: var(--primary-dim); letter-spacing: .16em;
  padding: 12px 18px; border-bottom: 1px solid var(--faint); background: var(--void-warm);
}
.grid { display: grid; grid-template-columns: 200px 1fr 256px; gap: 2px; padding: 2px; background: var(--void); }
.panel { background: var(--void-warm); border: 1px solid var(--faint); min-height: 360px; }
.panel-h {
  font-size: 10px; text-transform: uppercase; color: var(--primary-dim); letter-spacing: .16em;
  padding: 10px 14px; border-bottom: 1px solid var(--faint);
  display: flex; justify-content: space-between;
}

/* INDEX CORE */
.repo { padding: 12px 14px; border-bottom: 1px solid var(--faint); }
.repo .nm { font-size: 11.5px; color: var(--text-dim); }
.repo .mt { font-size: 9.5px; color: #4a4a4a; margin-top: 4px; }
.repo .bar { height: 2px; background: #161616; margin-top: 8px; }
.repo .bar i { display: block; height: 2px; background: #333; width: 0; transition: width .4s ease; }
.repo.fire { border-left: 2px solid var(--green-dim); }
.repo.fire .nm { color: var(--green-dim); }
.repo.fire .bar i { background: var(--green-dim); }

/* RECALL */
.recall { padding: 18px; }
.turn { margin-bottom: 22px; }
.turn .q { color: var(--text); }
.turn .q b { color: var(--primary); }
.trace { width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 10.5px; }
.trace td { padding: 5px 6px; border-bottom: 1px solid var(--faint); color: var(--text-dim); }
.trace td.path { color: var(--cyan-dim); }
.trace td.sim { color: var(--green-dim); text-align: right; }
.ai { line-height: 1.85; margin-top: 10px; color: #cfcfcf; }
.ai .tag {
  font-family: 'Saira Extra Condensed', sans-serif; font-weight: 600;
  color: var(--purple-dim); border: 1px solid var(--purple-dim);
  padding: 1px 6px; font-size: 10px; margin-right: 6px;
}
.cite {
  color: var(--green-dim); cursor: pointer; font-size: 11px;
  border-bottom: 1px dotted var(--green-dim);
}
.cite:hover { color: var(--green); }
.empty { display: flex; flex-direction: column; justify-content: center; min-height: 200px; color: #4a4a4a; }
.empty .ex { color: var(--cyan-dim); font-size: 11px; margin-top: 8px; cursor: pointer; }
.empty .ex:hover { color: var(--cyan); }

/* SOURCE LOCK */
.lock { position: relative; margin: 14px; border: 1px solid var(--cyan-dim); padding: 14px; }
.lock::before, .lock::after { content: ""; position: absolute; width: 10px; height: 10px; }
.lock::before { top: -1px; left: -1px; border-top: 2px solid var(--cyan); border-left: 2px solid var(--cyan); }
.lock::after { bottom: -1px; right: -1px; border-bottom: 2px solid var(--cyan); border-right: 2px solid var(--cyan); }
.lock .pth { color: var(--cyan-dim); font-size: 11px; }
.lock .rng { color: #4a4a4a; font-size: 9.5px; margin-top: 3px; }
.lock pre { margin: 10px 0 0; font-size: 10px; line-height: 1.7; color: var(--text-dim); white-space: pre-wrap; }
.lock-empty { padding: 40px 14px; color: #4a4a4a; text-align: center; }
.gh { padding: 0 14px 14px; }
.gh a { color: var(--cyan-dim); font-size: 10px; text-decoration: none; }
.gh a:hover { color: var(--cyan); }

/* COMMAND BAR */
.cmd { display: flex; align-items: center; gap: 12px; background: var(--void-warm); border: 1px solid var(--faint); margin: 0 2px 2px; padding: 14px 18px; }
.cmd .prompt { color: var(--primary-dim); }
.cmd input {
  flex: 1; background: transparent; border: none; outline: none;
  color: var(--text); font-family: 'JetBrains Mono', monospace; font-size: 12.5px;
}
.cmd input::placeholder { color: var(--text-dim); }
.cmd button {
  border: 1px solid var(--primary-dim); color: var(--primary-dim); background: transparent;
  padding: 5px 14px; font-size: 11px; cursor: pointer;
}
.cmd button:hover { border-color: var(--primary); color: var(--primary); }
.cmd button:disabled { opacity: .4; cursor: default; }

/* FOOTER */
.footer { display: flex; gap: 18px; justify-content: center; padding: 18px; font-size: 10px; color: #4a4a4a; border-top: 1px solid var(--faint); }
.footer a { color: var(--text-dim); text-decoration: none; }
.footer a:hover { color: var(--primary-dim); }

/* thinking pulse for the searching state */
.pulse { color: var(--purple-dim); }
.pulse::after { content: "▍"; animation: blink 1s steps(2) infinite; }
@keyframes blink { 0%, 50% { opacity: 1; } 50.01%, 100% { opacity: 0; } }
```

- [ ] **Step 2: Create `engram/web/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Engram · queryable memory of your code</title>
  <link rel="stylesheet" href="/styles.css" />
</head>
<body>

  <!-- HERO -->
  <header class="hero">
    <div class="kanji">記憶</div>
    <h1><span class="title sig">Engram</span></h1>
    <p class="pitch">
      grep finds strings. github search finds files.<br />
      <b>engram finds answers — with receipts.</b><br />
      a queryable memory of everything you've built.
    </p>
    <div class="diffs stamp">
      <div>personal <b>multi-repo</b> memory</div>
      <div>citations as a <b>contract</b></div>
      <div><b>self-hosted</b> · open models</div>
      <div><b>eval</b>-measured</div>
    </div>
    <div class="status stamp" id="status-line">
      <span id="repo-count">—</span> REPOS ·
      <span id="chunk-count">—</span> CHUNKS INDEXED ·
      <span class="off" id="online-indicator">○ CONNECTING</span>
    </div>
    <a class="cta stamp" href="#console">▾ begin recall</a>
  </header>

  <!-- RECALL CONSOLE -->
  <main id="console">
    <div class="console-h stamp">▸ RECALL CONSOLE</div>
    <div class="grid">

      <!-- INDEX CORE (left) -->
      <section class="panel">
        <div class="panel-h stamp">
          <span>◢ INDEX CORE</span><span id="core-count" style="color:var(--green-dim)">—</span>
        </div>
        <div id="index-core"><!-- repos injected by app.js --></div>
      </section>

      <!-- RECALL (center) -->
      <section class="panel">
        <div class="panel-h stamp">
          <span>▸ RECALL</span><span id="session-id" style="color:#4a4a4a">STANDBY</span>
        </div>
        <div class="recall" id="recall">
          <div class="empty">
            <div class="stamp" style="color:var(--text-dim)">awaiting query</div>
            <div class="ex">› how do nightwire's intensity modes scale neon?</div>
            <div class="ex">› where did I implement the agent loop?</div>
            <div class="ex">› find every place I call an LLM API</div>
          </div>
        </div>
      </section>

      <!-- SOURCE LOCK (right) -->
      <section class="panel">
        <div class="panel-h stamp">
          <span>⊹ SOURCE LOCK</span><span id="lock-badge" style="color:var(--green-dim)"></span>
        </div>
        <div id="source-lock">
          <div class="lock-empty stamp">no source locked</div>
        </div>
      </section>

    </div>

    <!-- COMMAND BAR -->
    <form class="cmd" id="cmd-form">
      <span class="prompt">❯</span>
      <input id="cmd-input" type="text" placeholder="interrogate your memory…" autocomplete="off" />
      <button class="stamp" type="submit" id="cmd-send">RECALL</button>
    </form>
  </main>

  <!-- FOOTER -->
  <footer class="footer">
    <a href="https://github.com/cativo23/engram" target="_blank" rel="noopener">GITHUB ↗</a>
    <a href="https://github.com/cativo23/engram/blob/main/docs/PRD.md" target="_blank" rel="noopener">ARCHITECTURE</a>
    <a href="https://github.com/cativo23/nightwire" target="_blank" rel="noopener">NIGHTWIRE ↗</a>
  </footer>

  <script type="module" src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Eyeball the static page (no server yet)**

Run: `.venv/bin/python -c "import pathlib, webbrowser; webbrowser.open(pathlib.Path('engram/web/index.html').resolve().as_uri())"`
Expected: the hero renders with the Engram sigil, 記憶 kanji, four stamps, and the empty console below. Fonts load from Google Fonts. (Live data shows as `—` placeholders; that's expected until Task 7/8.)

- [ ] **Step 4: Commit**

```bash
git add engram/web/index.html engram/web/styles.css
git commit -m "feat(web): nightwire hero + recall console markup (archive mode)"
```

---

## Task 7: DOM rendering + live wiring

**Files:**
- Create: `engram/web/render.js`
- Create: `engram/web/app.js`

- [ ] **Step 1: Create `engram/web/render.js`**

```javascript
// DOM rendering from recall state. Pure-ish: reads state, writes the DOM.
// (Visual layer — verified by browser QA, not unit tests.)

const $ = (id) => document.getElementById(id);

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// Turn [n] markers in answer text into clickable citation badges.
function renderAnswer(text) {
  return escapeHtml(text).replace(/\[(\d+)\]/g, (_, n) => `<span class="cite" data-n="${n}">[${n}]</span>`);
}

export function renderIndexCore(state) {
  $("core-count").textContent = String(state.repos.length).padStart(2, "0");
  $("index-core").innerHTML = state.repos
    .map((r) => {
      const pct = r.score != null ? Math.round(r.score * 100) : 0;
      return `<div class="repo${r.fired ? " fire" : ""}">
        <div class="nm">${escapeHtml(r.name)}</div>
        <div class="mt">${escapeHtml(r.lang || "")} · ${r.chunks ?? 0} chunks${
        r.score != null ? " · " + r.score.toFixed(2) : ""
      }</div>
        <div class="bar"><i style="width:${pct}%"></i></div>
      </div>`;
    })
    .join("");
}

export function renderRecall(state) {
  const recall = $("recall");
  if (state.status === "standby") return; // keep the empty/example state
  const traceRows = state.trace
    .map((t) => `<tr><td class="stamp" style="color:var(--purple-dim)">${escapeHtml(t.name)}</td>
      <td class="path">${escapeHtml(t.query)}</td><td class="sim"></td></tr>`)
    .join("");
  const cityRows = state.citations
    .map((c) => `<tr><td></td><td class="path">${escapeHtml(c.repo)}/${escapeHtml(c.path)}</td>
      <td class="sim">${c.similarity != null ? c.similarity.toFixed(2) : ""}</td></tr>`)
    .join("");
  const thinking = state.status === "searching" && !state.answer
    ? `<div class="ai"><span class="tag">AI</span><span class="pulse">recalling</span></div>`
    : "";
  const answer = state.answer
    ? `<div class="ai"><span class="tag">AI</span>${renderAnswer(state.answer)}</div>`
    : "";
  const errorBlock = state.status === "error"
    ? `<div class="ai" style="color:var(--text-dim)">recall failed — ${escapeHtml(state.error || "")}</div>`
    : "";
  recall.innerHTML = `<div class="turn">
    <div class="q"><b>❯</b> ${escapeHtml(state.query || "")}</div>
    <table class="trace">${traceRows}${cityRows}</table>
    ${thinking}${answer}${errorBlock}
  </div>`;
}

export function renderSourceLock(state) {
  const el = $("source-lock");
  const badge = $("lock-badge");
  const c = state.sourceLock;
  if (!c) {
    el.innerHTML = `<div class="lock-empty stamp">no source locked</div>`;
    badge.textContent = "";
    return;
  }
  badge.textContent = `[${c.n}] ${c.similarity != null ? c.similarity.toFixed(2) : ""}`;
  const startLine = c.line_start ?? 1;
  const numbered = (c.snippet || "")
    .split("\n")
    .map((line, i) => `<span style="color:var(--green-dim)">${startLine + i}</span> ${escapeHtml(line)}`)
    .join("\n");
  el.innerHTML = `<div class="lock">
      <div class="pth">${escapeHtml(c.repo)} · ${escapeHtml(c.path)}</div>
      <div class="rng">L${c.line_start}–${c.line_end}</div>
      <pre>${numbered}</pre>
    </div>
    <div class="gh"><a href="${escapeHtml(c.github_url)}" target="_blank" rel="noopener" class="stamp">OPEN ▸ GITHUB ↗</a></div>`;
}

export function renderAll(state) {
  renderIndexCore(state);
  renderRecall(state);
  renderSourceLock(state);
}
```

- [ ] **Step 2: Create `engram/web/app.js`**

```javascript
// Entry point: health check, repo bootstrap, input wiring, and the SSE round-trip.
import { streamSSE } from "./sse.js";
import { initialState, reduce, lockSource } from "./recall.js";
import { renderAll } from "./render.js";

// Repos shown in INDEX CORE. (Static for v1; P2/P4 can expose a /repos endpoint.)
const REPOS = [
  { name: "nightwire", lang: "CSS", chunks: 142 },
  { name: "llm-from-scratch", lang: "PY", chunks: 96 },
  { name: "engram", lang: "PY", chunks: 51 },
  { name: "dotfiles", lang: "SH", chunks: 23 },
];

let state = initialState(REPOS);
let conversationId = null;

function setState(next) {
  state = next;
  renderAll(state);
}

async function checkHealth() {
  const indicator = document.getElementById("online-indicator");
  try {
    const r = await fetch("/health");
    const ok = r.ok && (await r.json()).status === "ok";
    indicator.textContent = ok ? "● ONLINE" : "○ DEGRADED";
    indicator.className = ok ? "on" : "off";
  } catch {
    indicator.textContent = "○ OFFLINE";
    indicator.className = "off";
  }
  document.getElementById("repo-count").textContent = String(REPOS.length).padStart(2, "0");
  document.getElementById("chunk-count").textContent = REPOS.reduce((a, r) => a + (r.chunks || 0), 0);
  document.getElementById("core-count").textContent = String(REPOS.length).padStart(2, "0");
}

async function recall(query) {
  const input = document.getElementById("cmd-input");
  const send = document.getElementById("cmd-send");
  input.value = "";
  send.disabled = true;
  document.getElementById("session-id").textContent = "ACTIVE";

  // Reset to a fresh turn but keep the question visible.
  setState({ ...reduce(state, { event: "start", data: { conversation_id: conversationId } }), query });

  try {
    const resp = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: query, conversation_id: conversationId }),
    });
    for await (const ev of streamSSE(resp)) {
      if (ev.event === "start" && ev.data?.conversation_id) {
        conversationId = ev.data.conversation_id;
      }
      setState({ ...reduce(state, ev), query });
    }
  } catch (err) {
    setState({ ...reduce(state, { event: "error", data: { message: String(err) } }), query });
  } finally {
    send.disabled = false;
    input.focus();
  }
}

function wire() {
  document.getElementById("cmd-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = document.getElementById("cmd-input").value.trim();
    if (q) recall(q);
  });

  // Click an example query in the empty state.
  document.getElementById("recall").addEventListener("click", (e) => {
    const ex = e.target.closest(".ex");
    if (ex) recall(ex.textContent.replace(/^›\s*/, "").trim());
    const cite = e.target.closest(".cite");
    if (cite) setState({ ...lockSource(state, Number(cite.dataset.n)), query: state.query });
  });

  document.getElementById("cmd-input").focus();
}

checkHealth();
renderAll(state);
wire();
```

- [ ] **Step 3: Re-run the JS logic tests (no regressions in pure modules)**

Run: `npm test`
Expected: PASS (sse + recall suites still green — render/app aren't unit-tested but importing them must not break the others).

- [ ] **Step 4: Commit**

```bash
git add engram/web/render.js engram/web/app.js
git commit -m "feat(web): DOM rendering and live SSE wiring for the recall console"
```

---

## Task 8: Serve the UI from FastAPI + end-to-end run

**Files:**
- Modify: `engram/main.py`

- [ ] **Step 1: Mount the static UI (after the API routes)**

Add these two lines to the END of `engram/main.py` (after the `/chat` route):

```python
from fastapi.staticfiles import StaticFiles  # noqa: E402  (kept next to the mount)

# Static UI mounted LAST so /health and /chat match first.
app.mount("/", StaticFiles(directory="engram/web", html=True), name="web")
```

- [ ] **Step 2: Confirm the backend suite still passes with the mount present**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS — `engram/web/` now exists so `StaticFiles` initializes; `/health` and `/chat` tests still green (routes registered before the mount win).

- [ ] **Step 3: Start the server**

Run: `.venv/bin/uvicorn engram.main:app --reload --port 8000`
Expected: `Uvicorn running on http://127.0.0.1:8000`. Leave it running.

- [ ] **Step 4: Smoke-test the SSE endpoint from the shell**

In a second shell, run:
`curl -N -s -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' -d '{"message":"where is the agent loop?"}'`
Expected: a sequence of SSE frames — `event: start`, `event: tool`, `event: citations` (with the stub hits), several `event: token`, and `event: done`.

- [ ] **Step 5: Manual browser QA** (use the `browser-qa-agent` per routing rules)

Open `http://127.0.0.1:8000/` and verify the checklist:
  - Hero renders; status line shows `04 REPOS · 312 CHUNKS · ● ONLINE`.
  - INDEX CORE lists the four repos.
  - Submit *"where is the agent loop?"* → the question appears, a retrieval-trace row shows, repos with citations **fire** green with a similarity bar, the answer streams in with a purple `AI` tag and at least one `[1]` badge.
  - SOURCE LOCK shows the cited chunk with line numbers, range, and an `OPEN ▸ GITHUB ↗` link to the right file.
  - Click a `[n]` badge → SOURCE LOCK switches to that citation.
  - A follow-up question reuses the same conversation (the answer reflects prior context).

- [ ] **Step 6: Stop the server (Ctrl-C) and commit**

```bash
git add engram/main.py
git commit -m "feat(api): serve the static recall console UI from FastAPI"
```

---

## Task 9: README + final polish

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the UI + dev workflow in the README**

Add a `## Web UI` section to `README.md` covering:

```markdown
## Web UI

Engram ships a static "recall console" served by FastAPI at `/` (no build step).
It consumes the SSE `/chat` contract: `start` → `tool`/`citations` → `token`… → `done`.

```bash
uvicorn engram.main:app --reload      # then open http://127.0.0.1:8000/
```

Design: built on [nightwire](https://github.com/cativo23/nightwire), the author's
cyberpunk design system (ARCHIVE intensity). See
`docs/superpowers/specs/2026-06-08-engram-frontend-design.md`.

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest                  # backend tests (tools, agent, SSE)
npm install && npm test # frontend logic tests (SSE parser, state reducer)
```
```

- [ ] **Step 2: Run the full test matrix one last time**

Run: `.venv/bin/python -m pytest -q && npm test`
Expected: backend green + frontend green.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document the web UI and dev/test workflow"
```

- [ ] **Step 4: Push (remember the gh account switch)**

```bash
gh auth switch --user cativo23
git push
```

---

## Self-Review

**Spec coverage:**
- nightwire DS (vendored tokens, ARCHIVE dim palette) → Task 6 `styles.css`. ✓
- NERV 3-zone console (INDEX CORE / RECALL / SOURCE LOCK) → Task 6 HTML + Task 7 render. ✓
- ARCHIVE fixed, no switcher → no mode toggle anywhere; dim palette baked in. ✓
- Hybrid single page (hero + console) → Task 6 `index.html`. ✓
- **Signature: repos fire** → `fireRepos` (Task 5, unit-tested) + `.repo.fire` CSS + `renderIndexCore` (Tasks 6–7). ✓
- Static HTML/CSS/JS served by FastAPI → Task 8 mount. ✓
- States (standby/searching/streaming/multi-turn/refusal) → reducer statuses + render branches (Tasks 5,7); multi-turn via conversation_id (Task 7 + backend persistence Task 3). ✓
- Backend integration (`/health` ONLINE, `/chat` stream, structured citations) → Tasks 1–3 (SSE) + Task 7 (`checkHealth`, `streamSSE`). ✓
- Hero pitch, four differentiator stamps, status line, `▾ begin recall` CTA → Task 6 HTML. ✓
- SOURCE LOCK bracket-corner reticle, line numbers, GitHub link → `.lock::before/::after` CSS + `renderSourceLock`. ✓
- Footer (GitHub · architecture · nightwire) → Task 6 HTML. ✓

**Open items from the spec (resolved here):**
- Hero→console transition: **single scroll** with a `#console` anchor CTA (Task 6). ✓
- Structured citation payload shape: **defined** as the SSE contract above and in `tools.py` (Task 1). ✓
- How tool steps surface in the trace: `tool` events render as retrieval-trace rows (Task 7 `renderRecall`). ✓

**Placeholder scan:** No `TBD`/`add error handling`/`similar to Task N` — every code step contains full file contents or exact additions. Error handling is concrete (`try/except` in `/chat`, `error` event in reducer/render, bad-JSON tolerance in `parseSSE`).

**Type/name consistency:** `run_agent(messages, client=None)` (defined Task 2, monkeypatched Task 3, called Task 3 `generate`). Event types `tool|citations|token` consistent across agent → main → reducer. Hit keys (`repo,path,line_start,line_end,similarity,snippet,github_url`) identical in `tools.py`, tests, reducer, and `renderSourceLock`. `fireRepos`/`reduce`/`lockSource`/`initialState` names match between `recall.js` and `recall.test.js`. SSE event names (`start,tool,citations,token,done,error`) match `sse()` emitters (Task 3) and reducer cases (Task 5).
