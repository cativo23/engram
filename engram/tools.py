"""Tools the agent can call.

In P1, `search_code` is a STUB so the agent loop can be exercised end-to-end.
P2 replaces its body with real pgvector similarity search — the signature and
schema stay the same, so nothing else changes.
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


def search_code(query: str) -> str:
    """P1 STUB — returns a placeholder hit. Real vector search arrives in P2."""
    return (
        "[STUB RESULT — no real index yet; real search lands in P2]\n"
        f"Pretend match for {query!r}:\n"
        "carlos/llm-from-scratch · 02_agent.py:76-102 · the agent loop (`take_turn`): "
        "calls the model with tools, runs requested tools, feeds results back, repeats."
    )


TOOL_FUNCTIONS = {"search_code": search_code}


def run_tool(name: str, arguments: str) -> str:
    """Dispatch a tool call by name with its JSON-string arguments."""
    args = json.loads(arguments or "{}")
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"[error] unknown tool: {name}"
    return fn(**args)
