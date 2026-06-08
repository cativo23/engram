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
    "about the code, but call search_code at most twice — as soon as you have "
    "results, write your answer instead of searching again. Ground every factual "
    "claim in the search results. The search "
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
    final_text = None

    # 1) Tool-resolution rounds (bounded) — non-streamed so we can read tool_calls.
    for _ in range(settings.max_tool_iterations):
        resp = client.chat.completions.create(
            model=settings.model, messages=messages, tools=TOOLS_SCHEMA,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            final_text = msg.content  # the model answered in this same turn (may be None/"")
            break
        messages.append(msg)  # SDK message object verbatim — carries tool_calls for the next round-trip
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
            numbered = [{**h, "n": start + i} for i, h in enumerate(hits)]
            citation_count += len(hits)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": format_hits_for_model(hits, start_index=start),
            })
            if numbered:
                yield {"type": "citations", "citations": numbered}

    # 2a) The model already wrote its answer while finishing with tools — emit it
    #     directly. (Some models won't repeat it on a second call, returning empty.)
    if final_text:
        yield {"type": "token", "text": final_text}
        return

    # 2b) Otherwise force a streamed answer (no tools, so the model must produce text).
    stream = client.chat.completions.create(
        model=settings.model, messages=messages, stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield {"type": "token", "text": chunk.choices[0].delta.content}
