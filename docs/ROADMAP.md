# Engram — Roadmap

> **Location:** `~/engram-planning/ROADMAP.md` — deliberately OUTSIDE the git repo
> (`~/engram`) so it stays a private working doc, never committed. Repo:
> https://github.com/cativo23/engram

_Last updated: 2026-06-08_

---

## Status snapshot

| Area | State |
|---|---|
| **P1 — service skeleton** | ✅ Done. FastAPI, in-memory conversation store, agentic tool loop, `/health`. |
| **SSE `/chat`** | ✅ Done. Structured events (`start → tool → citations → token… → done`, `error`). `run_agent` yields typed events. |
| **Frontend (recall console)** | ✅ Done. nightwire ARCHIVE console, firing repos, source lock. PR #1 open. |
| **Docker stack** | ✅ Scaffolded. `docker compose up` → app + Postgres/pgvector (extension initialized). DB provisioned but **unused** (app doesn't query it yet). |
| **`search_code`** | ⚠️ **STUB** — returns 2 fixed hits regardless of query. This is what P2 makes real. |
| **Eval harness** | ❌ Not started (P3). |
| **Guardrails / observability / polished README** | ❌ Partial (Docker done early; rest is P4). |

**Key fact for P2:** the citation contract is already defined and consumed end-to-end
(`{repo, path, line_start, line_end, similarity, snippet, github_url, n}`). The frontend,
SSE layer, and model formatter all use it. **P2 only swaps the *values* from stub to real
vector search — no downstream changes needed.** The stub was designed for exactly this.

---

## P2 — Ingestion + pgvector (NEXT)

**Goal:** Turn Engram from "demo with a stub" into real RAG over Carlos's GitHub repos.
A few repos get cloned, chunked, embedded, and stored in pgvector; `search_code` becomes
a real cosine-similarity search returning the same structured hits the frontend already renders.

**Outcome that proves it's done:** ask "how do nightwire's intensity modes scale neon?" and
get a grounded answer citing the *actual* nightwire file/lines (not the agent-loop stub),
with the repo firing for real.

### Decisions to lock before planning P2
1. **Which repos to index.** In P2 the ingestion engine is **config/CLI-driven** —
   build and test it against 1–2 known repos (e.g. `nightwire`, `engram`). Runtime
   *selection* of repos moves to **P2.5 (Admin UI)** — see below. So P2 doesn't need
   a final repo list, just a couple to validate the pipeline.
2. **Chunking strategy:**
   - *Simple:* fixed line windows (e.g. 40 lines, 10 overlap) — fast, language-agnostic, good enough for v1.
   - *Code-aware:* tree-sitter split by function/class — better citations, more work + a dep.
   - **Recommendation:** ship simple line-window chunking in P2; note tree-sitter as a P2.5/P3 upgrade. Keeps P2 focused.
3. **Embedding model — LOCKED:** fastembed `jinaai/jina-embeddings-v2-base-code`, **768-dim** (`vector(768)` in the schema). Chosen via research: only code-specialized model in fastembed (150M+ code/QA pairs, 30 langs), 8192-token context (whole functions fit, no mid-function truncation). Free/local/Apache-2.0. Tradeoff: 640 MB first-run download → cache in a Docker volume. No query/passage prefixes needed (unlike BGE/nomic). 8192 ctx gives the line-window chunker generous headroom.
4. **Vector index:** HNSW (`vector_cosine_ops`) — good recall/speed for this scale.
5. **Citation `github_url` sha:** clone/pull each repo at a ref and pin the indexed commit sha into the URL (`/blob/<sha>/...`) so links never rot. Store the sha per repo.
6. **Re-index idempotency:** per-file content hash — skip files whose hash is unchanged since last index.

### Workstreams / build order
1. **DB schema + migrations** (alembic or raw SQL via `docker/init`):
   - `repos` (id, owner/name, indexed_sha, indexed_at)
   - `chunks` (id, repo_id, path, line_start, line_end, content, embedding `vector(384)`, content_hash)
   - HNSW index on `chunks.embedding`.
   - Add `psycopg[binary]`, `pgvector`, `fastembed`, `numpy` to `requirements.txt` (already noted as P2 in the comment).
2. **DB access layer:** a thin module + FastAPI dependency for a connection/session. Wire `DATABASE_URL` into `config.py` (compose already injects it).
3. **Ingestion pipeline** (`engram/ingest/` + a CLI entrypoint, e.g. `python -m engram.ingest`):
   clone/pull → walk files → filter (gitignore rules, binary, size cap, lockfiles) → chunk → embed (batched) → upsert with hash gate.
4. **Real `search_code`:** embed the query → pgvector cosine top-k → map rows to the existing hit dict shape (pin sha into `github_url`). **Signature & return shape stay identical.**
5. **Config:** embedding model id, chunk size/overlap, top-k, repo list — all env/config, not hardcoded.
6. **Tests:**
   - Unit: chunker (boundaries/overlap), file filter, hash gate (re-index skips unchanged), URL builder.
   - Integration: ingest a tiny fixture repo into a test pgvector DB, then `search_code` returns the expected chunk. (Use the docker db or a testcontainer.)
7. **Wire-up check:** run the stack, ask a real question, confirm real citations + firing repos. Remove/retire the stub.

### Risks / notes
- fastembed first run downloads the model (~90 MB) → cache it (`.fastembed_cache/`, already gitignored) and/or bake into the Docker image.
- Keep PHI/secret rules irrelevant here (public code), but **never index `.env`/secrets** — the file filter must exclude them.
- The frontend's static `REPOS` list in `app.js` should eventually come from a `/repos` endpoint (P2 or P4) so INDEX CORE reflects the real index + chunk counts.

---

## P2.5 — Admin UI for repo selection

**Goal:** Pick which repos Engram indexes *at runtime*, instead of a config list —
reinforces the "self-hostable: clone it, index YOUR repos" pitch.

**Depends on P2:** the ingestion pipeline must already be a callable service
(`ingest_repo(owner/name)` + status/remove). The admin is a thin layer that drives it.

### Scope
- **Backend endpoints** (under an `/admin` prefix, protected):
  - `GET /admin/repos` — list indexed repos + status (chunks, indexed_sha, last indexed).
  - `POST /admin/repos` — add a repo by `owner/name`; kicks off ingestion (background task).
  - `DELETE /admin/repos/{id}` — remove a repo + its chunks.
  - `GET /admin/repos/{id}/status` — ingestion progress (queued/running/done/failed).
- **Admin UI:** a second nightwire page (or a panel) — add-repo input, list with status + re-index/remove, live progress. Reuses the design system.
- **Make INDEX CORE data-driven:** the hero/console pull the repo list from `GET /repos` (public, read-only) instead of the hardcoded `app.js` array.
- **Ingestion as background work:** indexing is slow (clone + embed) — run it async (FastAPI `BackgroundTasks` or a small task queue) and report progress, don't block the request.

### Decisions to lock before planning P2.5
1. **Auth model** (the important one — admin triggers expensive ops + clones arbitrary repos):
   - *Simple:* a single admin token via env var (`ADMIN_TOKEN`), sent as a header/Bearer. Easy, fine for self-host.
   - *Local-only:* admin routes enabled only when a flag/`ENV=dev` is set, disabled in public deploys.
   - *Full:* Passport/JWT + roles (overkill for a portfolio tool).
   - **Recommendation:** env `ADMIN_TOKEN` (simple, self-host-friendly), + a flag to disable admin entirely for the public demo deploy.
2. **Repo source:** manual `owner/name` slug entry (clone public repos) for v1, vs. "list my GitHub repos" (needs a GitHub token/OAuth — a later enhancement).
3. **Abuse guard for public deploys:** allowlist of owners, repo size cap, max repo count.

---

## P3 — Eval harness

**Goal:** Make "citations as a contract" measurable — the CV differentiator.

- Reference dataset: hand-label ~20–30 (question → expected file/symbol) pairs across the indexed repos.
- Metrics: **recall@k** (did the right chunk get retrieved?), **citation accuracy** (do cited lines actually contain the claim?), **groundedness** (is every claim backed by a retrieved chunk — catch hallucination/refusal correctness).
- Runner: `python -m engram.eval` → prints a scorecard; wire into CI later.
- Surface results in the footer/README ("eval-measured" stamp the hero already promises).

---

## P4 — Guardrails, observability, polish

- **Guardrails:** input validation, max query length, rate limiting, max_tool_iterations already capped; refusal correctness covered by P3.
- **Observability:** structured logging, Sentry (per BM conventions), request/latency metrics, token/cost tracking per query.
- **Docker:** ✅ compose done early. Add multi-stage build, healthcheck on the app service, `.env.example` wired for compose.
- **README polish:** screenshots/GIF of the console, architecture diagram, the `docker compose up` quickstart (currently only `uvicorn` is documented), eval results.
- **Persistence:** move the in-memory `CONVERSATIONS` store to the DB (it's single-process today).
- **Frontend `/repos` endpoint** so INDEX CORE is data-driven.

---

## Cross-cutting backlog (not phase-bound)
- Pin SOURCE-LOCK href host to `github.com` (scheme guard already in place) — flagged in the frontend review.
- Stronger default `MODEL` guidance / let the model be chosen per-request; free tier 429-rate-limits under load.
- Optional: tree-sitter code-aware chunking (upgrade from line windows).
- Optional: `/repos` + live index status (chunk counts) for the hero status line.

---

## How to work each phase
Per phase: `superpowers:writing-plans` → `subagent-driven-development` (fresh subagent + 2-stage review per task) → live verify → `finishing-a-development-branch`. Same loop that shipped the frontend. Use **Sonnet** for implementers/reviewers (Opus only for genuine architecture decisions).
