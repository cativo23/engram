"""Engram API — a streaming /chat over Server-Sent Events.

Run:  uvicorn engram.main:app --reload
"""

import json
import logging
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import run_agent, system_message

logger = logging.getLogger("engram")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the vector schema on startup; non-fatal if the DB is unavailable."""
    try:
        from .db import connect, init_schema
        with connect() as conn:
            init_schema(conn)
    except Exception:
        logger.exception("schema init skipped (db unavailable)")
    yield


app = FastAPI(
    title="Engram",
    description="Query your code with citation-backed answers.",
    version="0.1.0",
    lifespan=lifespan,
)

# P1: in-memory conversation store (single process). P2+ can move this to a DB.
CONVERSATIONS: dict[str, list] = {}


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None       # omit to start a new conversation


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.get("/health")
def health() -> dict:
    """Liveness probe — drives the UI's ONLINE indicator."""
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """Stream the answer as SSE: start -> tool/citations -> token... -> (error?) -> done.

    `done` always fires last, even when an `error` frame precedes it.
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


# Static UI mounted LAST so /health and /chat match first.
app.mount("/", StaticFiles(directory=str(Path(__file__).parent / "web"), html=True), name="web")
