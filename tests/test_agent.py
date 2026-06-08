from types import SimpleNamespace

import engram.tools as tools
from engram.agent import run_agent

_FAKE_HITS = [
    {"repo": "cativo23/x", "path": "a.py", "line_start": 1, "line_end": 5,
     "similarity": 0.9, "snippet": "code-a", "github_url": "https://github.com/cativo23/x/blob/main/a.py#L1-L5"},
    {"repo": "cativo23/y", "path": "b.py", "line_start": 2, "line_end": 4,
     "similarity": 0.8, "snippet": "code-b", "github_url": "https://github.com/cativo23/y/blob/main/b.py#L2-L4"},
]


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


def test_tool_path_emits_tool_then_citations_then_tokens(monkeypatch):
    monkeypatch.setitem(tools.TOOL_FUNCTIONS, "search_code", lambda query: _FAKE_HITS)
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


def test_answer_produced_during_tool_resolution_is_emitted_without_extra_call(monkeypatch):
    monkeypatch.setitem(tools.TOOL_FUNCTIONS, "search_code", lambda query: _FAKE_HITS)
    # When the model finishes searching and writes its answer in the SAME
    # (non-streamed) turn that ends the tool loop, that text must be emitted —
    # not discarded in favour of a redundant streamed call that some models
    # return empty. Only TWO responses are scripted: if run_agent made a third
    # (streamed) call, FakeClient would IndexError — so this also proves no
    # extra call happens.
    client = FakeClient([
        _msg(tool_calls=[_tool_call("search_code", '{"query": "agent loop"}')]),
        _msg(content="The loop runs tools then answers[1].", tool_calls=None),
    ])
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
    events = list(run_agent(messages, client=client))
    assert [e["type"] for e in events] == ["tool", "citations", "token"]
    assert events[-1]["text"] == "The loop runs tools then answers[1]."
