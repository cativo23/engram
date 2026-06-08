# Engram Frontend — Design Spec

**Date:** 2026-06-08
**Status:** Approved (aesthetic + scope locked). Next: implementation plan.
**Topic:** The web UI for Engram (the agentic code-RAG service).

---

## Purpose & audience

A web interface for Engram that doubles as a **portfolio/CV centerpiece**. The
primary visitor is a **cold hiring manager / recruiter** who lands without
context and decides in seconds whether this is impressive. Secondary: Carlos
himself using it, and engineers exploring the repo.

Implication: the UI must **sell** (what is this, why is it senior-grade) AND
**demonstrate** (a live, working recall console) — fast.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Design system | **nightwire** (Carlos's own — github.com/cativo23/nightwire) | Dogfoods his own cyberpunk DS; the portfolio shows TWO of his projects working together. Perfect match for the dark/neon direction. |
| Layout concept | **NERV-style "recall console"** (not a centered chatbot) | Distinctive, dense, data-rich; breaks the generic chat convention. |
| Intensity mode | **ARCHIVE, fixed** (no switcher) | Engram *is* a calm, queryable archive of memory. Reading/recall tool, not a live-alert dashboard. Calm = refined + readable + truest to nightwire's soft-neon/tonal/zero-waste ethos. (A mode switcher with no real function would be decorative waste — rejected.) |
| Page scope | **Hybrid single page**: hero (sells) + recall console (demos) | A (console only) undersells to a cold visitor; B (separate landing + app, possibly React) over-builds and fights nightwire's plain-CSS nature. Hybrid = max legibility, one stack, minimal maintenance. |
| Signature element | **Repos in the INDEX CORE "fire"** (light up green) when relevant to a query | The "engram = memory trace that fires" concept, visualized. The one thing a visitor remembers. |
| Tech stack | **Static HTML/CSS/JS**, no build, served by FastAPI; consumes nightwire (plain CSS / its tokens) | Zero build friction, easy to demo/deploy, lets nightwire shine. Avoids a React pipeline that adds nothing at this scope. |

## nightwire design language (the tokens we use)

Pure black surfaces (`#000`, void-warm `#0a0a0a`), elevation through **tonal
progression, never shadows**. Soft neon. 2px signature gap between panels.
Mostly square corners.

- **Typography:** `JetBrains Mono` (sys/body/data/code) · `Noto Serif Display`
  900 uppercase, compressed `scaleX(.82)` (the "Engram" sigil / titles) ·
  `Saira Extra Condensed` uppercase (stamps: labels, badges, buttons) ·
  `Shippori Mincho B1` for the 記憶 kanji accent.
- **Color roles:** primary blue `#6699ff` = chrome/headers/labels/focus ·
  **purple `#b266e0` = AI elements** · green `#7aed7a` = data values
  (counts, line numbers, similarity) · cyan `#66ddff` = metadata (repo/path) ·
  amber `#e8993a` = warning · red `#ff6688` = error.
- **ARCHIVE intensity:** use the **dim variants** (`primary-dim #4477cc`,
  `green-dim #5cb85c`, `cyan-dim #44aacc`, `purple-dim #8844bb`) as the default
  palette, generous spacing, minimal/no glow. Full-neon reserved for the single
  most important accent in view.

## Page structure (top → bottom, one scroll)

1. **Hero / standby band**
   - 記憶 kanji eyebrow, the `Engram` sigil (compressed serif display).
   - One-line pitch: *"grep finds strings. github search finds files. engram
     finds answers — with receipts. a queryable memory of everything you've built."*
   - Four differentiator readouts (NERV stamps, not prose): `personal multi-repo
     memory` · `citations as a contract` · `self-hosted · open models` ·
     `eval-measured`.
   - Status line: `04 REPOS · 312 CHUNKS INDEXED · ● ONLINE` (live from backend).
   - CTA: `▾ begin recall`.

2. **Recall console — 3 zones** (the app)
   - **◢ INDEX CORE (left rail):** indexed repos as a living list — name, lang,
     chunk count, a thin activity bar. On a query, the relevant repo(s) **fire**
     (green-dim, left border, name brightens) with their similarity; others dim.
     *(Signature element.)*
   - **▸ RECALL (center):** the conversation as an ops trace — the `❯` query, a
     compact retrieval-trace table (`search_code` → path → sim), then the answer
     with a purple `AI` marker and inline citation badges `[1]`.
   - **⊹ SOURCE LOCK (right):** the cited chunk with a **bracket-corner reticle**
     (lock-on), `repo · path`, line range, line numbers (green-dim), sim score,
     and `OPEN ▸ GITHUB ↗` (pinned to the indexed sha).

3. **Command input bar:** `❯` prompt, placeholder *"interrogate your memory…"*,
   a `RECALL` stamp button.

4. **Footer (thin):** GitHub · architecture · eval results.

## States

- **Standby / empty:** hero + console with INDEX CORE populated, RECALL shows
  `awaiting query` + clickable example queries, SOURCE LOCK empty.
- **Searching:** tool-trace line appears; relevant repos begin to fire.
- **Streaming answer:** answer text streams token-by-token; citation badges
  appear; SOURCE LOCK locks onto `[1]`.
- **Multi-turn:** prior turns remain in RECALL; follow-ups work (backend memory).
- **No result / refusal:** the answer states it couldn't find it (cite-or-refuse
  guardrail); no SOURCE LOCK, no repos fired.

## Backend integration

Consumes the existing FastAPI service:
- `GET /health` → drives the `● ONLINE` indicator.
- `POST /chat` (streaming) → the answer stream for RECALL.
- **Citation/firing data:** the richest UX (populating SOURCE LOCK + firing
  repos) needs **structured** retrieval info, not just inline text citations.
  Per the PRD this is the planned SSE contract (`event: tool` status events +
  a `citations[]` array). **Decision:** the frontend targets that structured
  contract; if the backend isn't there yet, v1 can start by parsing inline
  `repo/path:line` citations from the text stream and firing repos from those,
  then upgrade to SSE events. (Backend work tracked separately in the roadmap.)

## Non-goals (frontend v1)

- No mode switcher (ARCHIVE is fixed).
- No auth / login / accounts UI.
- No settings panel, no repo-management UI (repos come from backend config).
- No mobile-first optimization (desktop-first; degrade gracefully).
- No real-time index status beyond the status line.

## Open items (decide during planning)

- Hero→console transition: single scroll vs. CTA reveal/scroll-to.
- Exact shape of the structured citation payload (align with backend P2/P4).
- How `read_file`/`list_repos` tool steps surface (if at all) in the trace.

## Reference mockups

Saved (gitignored) under `.superpowers/brainstorm/*/content/`:
`nightwire-engram.html`, `outside-box-console.html`, `archive-console.html`,
`hybrid-hero.html`. The **archive-console** + **hybrid-hero** pair is the
approved direction.
