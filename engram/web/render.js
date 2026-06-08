// DOM rendering from recall state. Pure-ish: reads state, writes the DOM.
// (Visual layer — verified by browser QA, not unit tests.)

const $ = (id) => document.getElementById(id);

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// Turn [n] markers in answer text into clickable citation badges.
function renderAnswer(text) {
  return escapeHtml(text).replace(/\[(\d+)\]/g, (_, n) => `<span class="cite" data-n="${n}">[${n}]</span>`);
}

export function renderIndexCore(state) {
  $("core-count").textContent = String(state.repos.length).padStart(2, "0");
  $("index-core").innerHTML = state.repos
    .map((r) => {
      const pct = r.score != null ? Math.round(r.score * 100) : 0;
      return `<div class="repo${r.fired ? " fire" : ""}">
        <div class="nm">${escapeHtml(r.name)}</div>
        <div class="mt">${escapeHtml(r.lang || "")} · ${r.chunks ?? 0} chunks${
        r.score != null ? " · " + r.score.toFixed(2) : ""
      }</div>
        <div class="bar"><i style="width:${pct}%"></i></div>
      </div>`;
    })
    .join("");
}

export function renderRecall(state) {
  const recall = $("recall");
  if (state.status === "standby") return; // keep the empty/example state
  const traceRows = state.trace
    .map((t) => `<tr><td class="stamp" style="color:var(--purple-dim)">${escapeHtml(t.name)}</td>
      <td class="path">${escapeHtml(t.query)}</td><td class="sim"></td></tr>`)
    .join("");
  const cityRows = state.citations
    .map((c) => `<tr><td></td><td class="path">${escapeHtml(c.repo)}/${escapeHtml(c.path)}</td>
      <td class="sim">${c.similarity != null ? c.similarity.toFixed(2) : ""}</td></tr>`)
    .join("");
  const thinking = state.status === "searching" && !state.answer
    ? `<div class="ai"><span class="tag">AI</span><span class="pulse">recalling</span></div>`
    : "";
  const answer = state.answer
    ? `<div class="ai"><span class="tag">AI</span>${renderAnswer(state.answer)}</div>`
    : "";
  // The model searched but produced no final text (common with small models that
  // loop on tool calls). Show an honest note instead of an empty, broken-looking pane.
  const noAnswer = state.status === "done" && !state.answer
    ? `<div class="ai" style="color:var(--text-dim)"><span class="tag">AI</span>no answer generated — the model searched but didn't produce a final response. Try rephrasing, or set a stronger <b style="color:var(--cyan-dim)">MODEL</b>.</div>`
    : "";
  const errorBlock = state.status === "error"
    ? `<div class="ai" style="color:var(--text-dim)"><span class="tag" style="color:var(--text-dim);border-color:var(--text-dim)">!</span>${escapeHtml(state.error || "")}</div>`
    : "";
  recall.innerHTML = `<div class="turn">
    <div class="q"><b>❯</b> ${escapeHtml(state.query || "")}</div>
    <table class="trace">${traceRows}${cityRows}</table>
    ${thinking}${answer}${noAnswer}${errorBlock}
  </div>`;
}

export function renderSourceLock(state) {
  const el = $("source-lock");
  const badge = $("lock-badge");
  const c = state.sourceLock;
  if (!c) {
    el.innerHTML = `<div class="lock-empty stamp">no source locked</div>`;
    badge.textContent = "";
    return;
  }
  badge.textContent = `[${c.n}] ${c.similarity != null ? c.similarity.toFixed(2) : ""}`;
  const safeUrl = /^https?:\/\//i.test(c.github_url || "") ? c.github_url : "#";
  const startLine = c.line_start ?? 1;
  const numbered = (c.snippet || "")
    .split("\n")
    .map((line, i) => `<span style="color:var(--green-dim)">${startLine + i}</span> ${escapeHtml(line)}`)
    .join("\n");
  el.innerHTML = `<div class="lock">
      <div class="pth">${escapeHtml(c.repo)} · ${escapeHtml(c.path)}</div>
      <div class="rng">L${c.line_start}–${c.line_end}</div>
      <pre>${numbered}</pre>
    </div>
    <div class="gh"><a href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener" class="stamp">OPEN ▸ GITHUB ↗</a></div>`;
}

export function renderAll(state) {
  renderIndexCore(state);
  renderRecall(state);
  renderSourceLock(state);
}
