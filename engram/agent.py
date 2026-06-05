"""The agent loop: resolve any tool calls, then stream the final answer.

Streaming + tool-calling together is fiddly, so P1 keeps it simple and honest:
run the tool-resolution rounds NON-streamed, then make one final STREAMED call
(without tools) so the model must produce the answer text we stream to the client.
(Trade-off: if the very first response needs no tool, we make one extra call to
stream it. Fine for the skeleton; can be optimised later.)
"""

from collections.abc import Iterator

from openai import OpenAI

from .config import settings
from .tools import TOOLS_SCHEMA, run_tool

client = OpenAI(
    base_url=settings.openrouter_base_url,
    api_key=settings.openrouter_api_key,
)

SYSTEM_PROMPT = (
    "You are Engram, an assistant that answers questions about a user's indexed "
    "code using the search_code tool. Always search before answering a question "
    "about the code. Ground every factual claim in the search results and include "
    "the repo/path:line citation the tool returns. If search_code finds nothing "
    "relevant, say you couldn't find it — never invent code or answer from prior "
    "knowledge. Keep answers concise."
)


def system_message() -> dict:
    """The seed message that opens every conversation."""
    return {"role": "system", "content": SYSTEM_PROMPT}


def stream_reply(messages: list) -> Iterator[str]:
    """Yield the assistant's answer token-by-token for one user turn.

    `messages` is mutated in place (tool requests + tool results are appended) so
    the caller can persist the whole conversation as memory.
    """
    # 1) Tool-resolution rounds (bounded) — non-streamed.
    for _ in range(settings.max_tool_iterations):
        resp = client.chat.completions.create(
            model=settings.model, messages=messages, tools=TOOLS_SCHEMA,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            break  # the model is ready to answer
        messages.append(msg)
        for call in msg.tool_calls:
            result = run_tool(call.function.name, call.function.arguments)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )

    # 2) Final answer — streamed (no tools, so it must produce text).
    stream = client.chat.completions.create(
        model=settings.model, messages=messages, stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
