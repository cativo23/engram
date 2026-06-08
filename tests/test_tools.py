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
