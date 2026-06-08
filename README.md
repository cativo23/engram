# Engram

> Turn your GitHub repos into a queryable, citation-backed knowledge base.
> **grep finds strings, GitHub search finds files — Engram finds answers with receipts.**

An open-source, self-hostable **agentic RAG** service that indexes your own
repositories and answers natural-language questions about your code — every claim
anchored to an exact `repo/path:line` citation.

> 🚧 **Status: work in progress.** P1 (service skeleton) is done; real retrieval
> lands in P2. See the [roadmap](#roadmap) and the full [PRD](docs/PRD.md).

---

## Why it exists

A senior engineer's solutions are scattered across dozens of repos. `grep` finds
strings; GitHub search finds files; neither explains *how the pieces fit* or
survives a follow-up question. Engram makes your body of work conversational —
ask in plain English, get a grounded answer with a citation you can click.

"Chat with your codebase" is a crowded category (Cody, Cursor, Continue). What
makes Engram different is the **framing and the rigor**:

1. **A personal, multi-repo knowledge base** — not an assistant inside one repo, but a queryable memory of *everything you've built*.
2. **Citations as a tested correctness contract** — exact `repo/file:line` provenance, enforced and measured (an answer without a citation is a failure).
3. **A real evaluation harness** — recall@k, citation accuracy, groundedness, gated in CI.
4. **Self-hostable, zero proprietary deps** — local embeddings + open models + pgvector in Docker.

---

## Architecture (target)

```
api (FastAPI)  →  agent (tool loop + memory)  →  retrieval / ingestion  →  embeddings / pgvector
```

- **Python + FastAPI** — streaming `/chat`.
- **Postgres + pgvector** (Docker) — vector store with HNSW index.
- **fastembed** — local embeddings (no embedding API).
- **OpenRouter** — any OpenAI-compatible model via the `MODEL` env var.
- **Agentic retrieval** — `search_code` / `read_file` / `list_repos` as tools the model calls.

Full design, decisions, and rationale: **[docs/PRD.md](docs/PRD.md)**.

---

## Quickstart (P1)

```bash
git clone https://github.com/cativo23/engram.git
cd engram

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then paste your OpenRouter key into .env

uvicorn engram.main:app --reload
```

Then, in another terminal:

```bash
# health check
curl localhost:8000/health

# chat (streams the answer; the X-Conversation-Id header lets you continue)
curl -N -X POST localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message": "how is the agent loop implemented?"}'
```

> In P1, `search_code` is a stub — it exercises the full agent loop end-to-end.
> Real pgvector-backed search arrives in P2.

---

## Web UI

Engram ships a static "recall console" served by FastAPI at `/` (no build step).
It consumes the SSE `/chat` contract: `start` → `tool`/`citations` → `token`… → `done`.

```bash
uvicorn engram.main:app --reload      # then open http://127.0.0.1:8000/
```

Design: built on [nightwire](https://github.com/cativo23/nightwire), the author's
cyberpunk design system (ARCHIVE intensity). See
`docs/superpowers/specs/2026-06-08-engram-frontend-design.md`.

The left **INDEX CORE** rail shows the indexed repos; on a query, the repos that
match light up ("fire") with their similarity score — the engram (memory-trace)
concept made visible. The center **RECALL** pane streams the answer with a
retrieval trace and `[n]` citation badges; the right **SOURCE LOCK** pane shows the
cited snippet with a deep link to the exact lines on GitHub.

> **Note on answer quality:** citation badges (`[n]`) and answer fidelity depend on
> the model following the cite-with-brackets instruction. Small free models
> (e.g. the default `gpt-oss-120b:free`) sometimes use non-standard citation
> markers or spend their turns on tool calls without a final answer. Set a stronger
> model via the `MODEL` env var for the best results. The structured panels
> (firing repos, retrieval trace, source lock) work regardless of the model.

---

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest                  # backend tests (tools, agent, SSE)
npm install && npm test # frontend logic tests (SSE parser, state reducer)
```

---

## Roadmap

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **P1** | FastAPI skeleton: streaming `/chat`, memory, tool loop, stub search | ✅ done |
| **P2** | Ingestion + pgvector: clone → chunk → embed → upsert; real `search_code` | ⏳ next |
| **P3** | Evaluation harness: recall@k, citation accuracy, groundedness | ⏳ |
| **P4** | Guardrails, observability, Dockerfile, polished README + demo | ⏳ |

---

## License

[MIT](LICENSE) © Carlos Cativo
