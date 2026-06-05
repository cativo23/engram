# Engram — turn your GitHub repos into a queryable, citation-backed knowledge base

> **Why "Engram":** a neuroscience term for a stored memory trace — the precise analog of an embedding — short, ownable, and signals senior AI judgment without being cute. Runners-up: **Mnemo** (cleaner brand, friendlier to say) and **Grimoire** (most personality, one step removed from "search my code"). Availability note: `engram`, `mnemo`, and `grimoire` are all taken on PyPI; as a repo/brand they are free. If a pip package is ever published, ship it as `engram-rag` and keep `Engram` as the repo/brand.

## Problem & value

A senior engineer's solutions are scattered across dozens of repos. Finding "how did I do JWT refresh?" means remembering which project it lived in, then cloning and grepping. `grep` finds strings; GitHub code search finds files; neither explains *how the pieces fit* or survives a follow-up question.

Engram makes your body of work conversational: ask in plain English, get an answer grounded in real code with an exact `repo / path:Lstart–Lend` citation. The honest one-liner — **grep finds strings, GitHub search finds files, this finds answers with receipts.**

Why it beats the alternatives:
- **Semantic, not lexical** — "where do I handle auth?" finds a `verifyBearer` guard that never contains the word "auth".
- **Cross-repo in one shot** — one question spans every indexed repo; no cloning, no per-repo syntax.
- **Grounded synthesis** — explains how loop → tool call → retrieval fit together, but every claim is anchored to a citation, so it's auditable.
- **Agentic reformulation** — search is a tool the model calls repeatedly ("auth" → "JWT" → "bearer token") instead of one dead-end lookup.
- **Conversational memory** — "now show me the test for that" works; grep has no memory.

## Target user & example queries

**Primary:** Carlos, recalling prior work across repos — and hiring managers / interviewers probing his engineering judgment without cloning ten projects. **Secondary:** a teammate onboarding onto one of his open-source repos.

Queries v1 must nail (all answerable from public code, every answer carrying a citation):

1. "Where did I implement JWT authentication?" → auth middleware/guard.
2. "Show me how I handle database migrations." → migration runner + example.
3. "How is the agent loop implemented in llm-from-scratch?" → core tool-calling loop.
4. "Where do I compute embeddings, and which model?" → call site + model config.
5. "How do I structure error handling in my FastAPI services?" → exception handlers/middleware.
6. "Find every place I call an external LLM API." → all client call sites, cross-repo.
7. "How is retrieval / vector search wired up?" → pgvector query + similarity logic.
8. "Compare how I do config/env loading across repos." → settings modules contrasted.
9. "What testing patterns do I use?" → fixtures, mocking, example test files.
10. "Now show me the test for that." → conversational follow-up on a prior answer.

**An answer without a citation is a failure, not a degraded success.**

## Scope (v1) and future

**v1 — demoable slice on public data:**
- Index a few hand-picked public repos (including the educational `llm-from-scratch`).
- FastAPI service with a streaming `/chat` endpoint; conversation memory.
- Agentic retrieval: `search_code`, `read_file`, `list_repos` exposed as tools the model calls.
- Postgres + pgvector (Docker), local embeddings via `fastembed`, OpenAI-compatible LLM through OpenRouter (`MODEL` env, default `openai/gpt-oss-120b:free`).
- Exact `repo/path:line` citations as a first-class, tested contract.
- A real evaluation harness with a versioned Q&A set.

**Future — scaling to all repos + notes:** Ingestion sits behind a `RepoSource` Protocol. v1's `GitSource` (reads `repos.yaml`, `git clone/pull`) swaps for a `GitHubApiSource` (`GET /user/repos` discovery, shallow-clone or Trees API) with **zero changes** downstream. The repo-level SHA gate plus file-level hash gate make nightly reindex over hundreds of repos near-free (only changed files re-embed; fastembed is local CPU, not API spend). Personal notes ingest through the same chunk → embed → upsert pipeline as another source. The only new code to go from a few repos to all is one `RepoSource` impl plus a scheduler.

## Non-goals

- **No private or PHI data** — public repos only; hard demo constraint.
- **No code generation, editing, or execution** — it explains and cites existing code; never writes, refactors, or runs it.
- **No general-purpose chat** — off-topic or out-of-corpus questions are politely declined.
- **No real-time mirror** — index on demand / on schedule; stated acceptable staleness.
- **No multi-tenant accounts / login UI in v1** — single-corpus, single-owner demo.
- **No deep GitHub-API crawl in v1** — architecture allows it; v1 doesn't ship it.
- **No fine-tuning** — off-the-shelf LLM + retrieval.

## Architecture overview

**Stack:** Python + FastAPI · Postgres + pgvector (Docker Compose) · `fastembed` local embeddings (bge-small-en-v1.5, 384-dim) · OpenAI-compatible LLM via OpenRouter (`MODEL` env) · SQLAlchemy + Alembic · pydantic-settings.

**Layering:** `api → agent → retrieval/ingestion → embeddings/db → domain`. Domain has zero dependencies; everything is wired in `deps.py` behind Protocols so the Git source swaps for the GitHub API source without touching callers.

**Ingestion pipeline:** `sync (clone/pull) → walk → filter → chunk → embed → upsert`. Filtering allowlists source extensions, honors `.gitignore`, skips vendor dirs/lockfiles/binaries/>1MB files. Two-level incremental gate: repo-level (`last_indexed_sha` vs HEAD; `git diff` for changed paths) and file-level (sha256 `file_hash` skips unchanged files — the gate that makes reindex cheap, since re-embedding is the expensive step). Each run writes an `ingest_runs` row (files seen, chunks written, duration) for observability.

**Chunking:** code-aware, not `char/N` (which severs signatures from bodies and embeds two scopes into one vector). Priority order: (1) language-aware split at function/class boundaries, carrying `symbol` + true line range, splitting oversized classes per-method with the class header retained; (2) line-window fallback (60 lines, 10-line overlap) for unsupported languages, markdown, config; (3) hard cap sub-splits anything over the embedding context (~512 tokens). `tree-sitter` is the clean upgrade behind the `Chunker` protocol — zero pipeline changes.

**Vector store:** pgvector with an **HNSW** index (`vector_cosine_ops`, `m=16`, `ef_construction=64`) — better recall/latency than ivfflat at this corpus size and no `lists` retraining as rows trickle in during incremental reindex. Chunks denormalize `repo/path/start_line/end_line/symbol/sha/file_hash` for cheap filtering and citation building; unique on `(repo_id, path, start_line, end_line)` to prevent duplicates.

**Agentic retrieval:** system prompt + history → model emits tool call(s) → dispatch → feed results back → repeat (cap ~5 iterations to bound cost/latency). Tools: `search_code(query, repo?, k)`, `read_file(repo, path, start, end)` (serves only paths present in `chunks` — no arbitrary disk read), `list_repos()`. Final answer streams token-by-token over SSE; tool steps stream as `event: tool` status events ("searching… reading attention.py"). **Guardrail:** every factual claim must cite a retrieved chunk; when `search_code` returns nothing, the model says it couldn't find it rather than answering from prior knowledge.

**Citation contract:** prose paired with a structured `citations[]` array; each citation's `url` is pinned to the indexed `sha` (not a branch), so it always resolves to the exact code that was indexed.

```
[1] carlos/llm-from-scratch · src/model/attention.py:88–141 · class MultiHeadAttention
```

## Roadmap

**P1 — Service skeleton.** FastAPI app, streaming `/chat` wired to OpenRouter, conversation memory, stubbed `search_code` tool, env-driven settings, `/health`.
*Done when:* `POST /chat` streams tokens across a multi-turn conversation; model invokes the stub tool and uses its results; secrets only in env; app boots from one command and `/health` returns 200.

**P2 — Ingestion + pgvector.** Docker Compose (Postgres + pgvector), ingestion CLI that clones/chunks/embeds/upserts the hand-picked repos; `search_code` becomes a real vector search.
*Done when:* `python -m ingest <repo>` populates pgvector with line-range metadata; re-running is idempotent (hash dedupe, no duplicate chunks); `search_code(query, k)` returns top-k with exact citations; `/chat` answers a real question about an indexed repo with a correct citation.

**P3 — Evaluation harness.** Versioned `eval/dataset.jsonl` + a runner scoring retrieval and answer quality, emitting a report.
*Done when:* `python -m eval run` produces recall@k, citation accuracy, and groundedness; dataset has ≥20 questions with gold `{repo, path, lines}`; results reproducible (fixed seed/model) under `eval/results/`; a regression threshold (e.g. recall@5 ≥ 0.8) is defined for CI to gate on.

**P4 — Guardrails / observability / packaging.** Cite-or-refuse + out-of-scope refusal, structured logging (latency/tokens/tool calls, no PHI/secrets), production `Dockerfile`, polished README (architecture diagram, demo GIF, eval table).
*Done when:* out-of-scope or uncited answers are blocked by an explicit rule with a test; each request logs latency/tokens/tool calls; `docker compose up` yields a working demo from scratch; a stranger can run it and grasp the design in <10 minutes.

> **MVP cut-line (inside P1–P2):** one repo (`llm-from-scratch`), single-turn, one tool call then answer, full (non-streamed) response — but **real embeddings, real vector search, and exact citations are non-negotiable; that triad is the product.** Streaming, multi-repo, memory, and the agentic loop are additive once the tool exists.

## Evaluation plan

**Reference set:** hand-authored `dataset.jsonl` (20–40 questions) over indexed repos, gold refs read from real code, not guessed:

```json
{"q": "How is multi-head attention split across heads?",
 "type": "factual",
 "gold_refs": [{"repo": "llm-from-scratch", "path": "src/attention.py", "lines": [40, 78]}],
 "must_mention": ["reshape", "num_heads"]}
```

Mix **factual** (single file), **cross-file** (concept spanning files), and **negative** (not in any repo → must refuse) — negatives are what expose hallucination.

| Metric | Measures | How |
|---|---|---|
| **Recall@k / hit-rate** | Retrieval surfaced a gold chunk in top-k | Path + line-range overlap with `gold_refs`; report @1/@3/@5 |
| **Citation accuracy** | Cited spans actually contain the claim | Cited path ∈ gold set AND line range overlaps; precision over emitted citations |
| **Groundedness** | Every claim supported by retrieved context | LLM-as-judge over (answer, chunks): supported / partial / unsupported |
| **Refusal correctness** | Negatives correctly declined | % of negatives answered "I don't know" |

Retrieval metrics are pure set math — free, deterministic, **gate CI on these**. Use a fixed-model LLM-as-judge with a rubric only for groundedness.

## Differentiation

"Chat with your codebase" is a crowded, commoditized category (Sourcegraph Cody — now enterprise-only; Cursor/Copilot Chat; Continue.dev; aider). Say so plainly in the README — honesty buys credibility. The novelty isn't the capability; it's the **framing, rigor, and auditability.**

1. **Personal multi-repo knowledge base (the headline).** Every commercial tool assists you *inside* a codebase you're editing. None is a queryable memory of *everything you've ever built*. This reframes the project from "another code-chat clone" to a personal engineering knowledge graph — distinctive on a CV.
2. **Citations as a tested correctness contract.** Few tools make exact, clickable `repo/file:line` provenance a hard, *measured* guarantee. This is the most CV-legible signal of senior judgment — "verification before assertion."
3. **A real evaluation harness.** The single biggest separator between a toy and a portfolio piece: golden Q&A set, recall@k/MRR, citation scoring, CI regression gating. Almost no hobby repo has this.
4. **Self-hostable, zero proprietary deps.** Local embeddings + swappable open model + pgvector in Docker — runs free on public data, no embedding API, no lock-in. Direct contrast with Cody's enterprise pivot; trivially reproducible by a reviewer.
5. **Agentic retrieval + clean, scale-ready architecture.** Search-as-a-tool (reformulation, multi-hop) + memory, with a documented v1→all-repos path, ADRs, and guardrails — architecture judgment, not just a demo.

**README hook:** lead with #1 (the personal-body-of-work framing). **CV bullet:** lead with #2 + #3 (citations + eval) — the clearest proof of engineering judgment.

> An open-source, self-hostable agentic RAG service that turns your GitHub repos into a queryable knowledge base — answering questions about your own code with exact `repo/file:line` citations, measured by a real evaluation harness.

## Definition of done for v1

- **Runs in one command** by a stranger on public data — `docker compose up`, ask a question, get a cited answer. No private code, no PHI.
- **Citations are verifiable** — every claim maps to a `repo/path:lines` a reviewer can open; the citation contract is enforced and tested.
- **Eval is visible and honest** — README shows a reproducible results table (recall@k, groundedness, citation accuracy), including known weak spots.
- **Architecture reads as senior** — clean boundaries (ingestion / retrieval / chat / eval), retrieval behind a swappable interface, GitHub-API scale-out documented as an extension point, not a TODO.
- **AI judgment is evident** — cite-or-refuse guardrail, tool-based agentic retrieval, and the eval contract show command of LLM failure modes.
- **Narratable in 2 minutes** — README opens with the problem, a demo GIF, the architecture diagram, and the eval table; each key decision (local embeddings, pgvector/HNSW, agentic tool, code-aware chunking) carries a one-line rationale.
