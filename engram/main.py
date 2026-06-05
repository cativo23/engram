"""Engram API — P1 skeleton: a streaming /chat endpoint with conversation memory.

Run:  uvicorn engram.main:app --reload
"""

import uuid
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import stream_reply, system_message

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


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """Stream the assistant's answer; memory is keyed by conversation_id.

    The conversation id is returned in the `X-Conversation-Id` header — pass it
    back on the next request to continue the same conversation.
    """
    conv_id = req.conversation_id or str(uuid.uuid4())
    messages = CONVERSATIONS.setdefault(conv_id, [system_message()])
    messages.append({"role": "user", "content": req.message})

    def generate() -> Iterator[str]:
        full: list[str] = []
        for piece in stream_reply(messages):
            full.append(piece)
            yield piece
        # Persist the assistant's reply so the next turn "remembers" it.
        messages.append({"role": "assistant", "content": "".join(full)})

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={"X-Conversation-Id": conv_id},
    )
