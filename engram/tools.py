"""Tools the agent can call.

`search_code` returns STRUCTURED hits (a list of dicts) so the API layer can emit
them as citation events, while `format_hits_for_model` turns them into the numbered
text the model reads (and cites with [n] markers). In P1 the hits are a STUB; P2
swaps the body for real pgvector similarity search — the return shape stays
identical, so nothing downstream changes.
"""

import inspect
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
    """Dispatch a tool call by name; return its STRUCTURED result (a list of hits).

    Models sometimes pass arguments the tool never declared (a hallucinated kwarg);
    we keep only the parameters the function actually accepts so a stray argument
    can't crash the agent loop.
    """
    args = json.loads(arguments or "{}")
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return []
    accepted = inspect.signature(fn).parameters
    kwargs = {k: v for k, v in args.items() if k in accepted}
    return fn(**kwargs)
