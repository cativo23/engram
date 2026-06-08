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
