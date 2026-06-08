"""Tools the agent can call.

`search_code` returns STRUCTURED hits (a list of dicts) so the API layer can emit
them as citation events, while `format_hits_for_model` turns them into the numbered
text the model reads (and cites with [n] markers). In P1 the hits were a STUB; P2
replaces the body with real pgvector cosine similarity search — the return shape
stays identical, so nothing downstream changes.
"""

import inspect
import json

from .config import settings
from .db import connect
from .ingest.embedder import embed_query


def _search_connect():
    """Indirection so tests can inject a live connection."""
    return connect()


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
    """Embed the query and return the cosine-nearest indexed chunks as hits.

    Return shape is identical to the P1 stub, so the agent/SSE/frontend are
    unchanged — only the values are now real.
    """
    vector = embed_query(query)
    # jina-code embeddings are L2-normalized, so cosine similarity (1 - <=> distance)
    # stays within ~[0,1]; a non-normalized model would break that assumption.
    sql = (
        "SELECT r.slug, r.indexed_sha, c.path, c.line_start, c.line_end, c.content, "
        "       1 - (c.embedding <=> %s) AS similarity "
        "FROM chunks c JOIN repos r ON r.id = c.repo_id "
        "ORDER BY c.embedding <=> %s LIMIT %s"
    )
    with _search_connect() as conn:
        # vector bound twice: once for the SELECT similarity column, once for ORDER BY
        rows = conn.execute(sql, (vector, vector, settings.search_top_k)).fetchall()

    hits = []
    for slug, sha, path, start, end, content, similarity in rows:
        ref = sha or "main"
        hits.append({
            "repo": slug,
            "path": path,
            "line_start": start,
            "line_end": end,
            "similarity": round(float(similarity), 4),
            "snippet": content,
            "github_url": f"https://github.com/{slug}/blob/{ref}/{path}#L{start}-L{end}",
        })
    return hits


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
