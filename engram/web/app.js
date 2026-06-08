// Entry point: health check, repo bootstrap, input wiring, and the SSE round-trip.
import { streamSSE } from "./sse.js";
import { initialState, reduce, lockSource } from "./recall.js";
import { renderAll } from "./render.js";

// Repos shown in INDEX CORE. (Static for v1; P2/P4 can expose a /repos endpoint.)
const REPOS = [
  { name: "nightwire", lang: "CSS", chunks: 142 },
  { name: "llm-from-scratch", lang: "PY", chunks: 96 },
  { name: "engram", lang: "PY", chunks: 51 },
  { name: "dotfiles", lang: "SH", chunks: 23 },
];

let state = initialState(REPOS);
let conversationId = null;

function setState(next) {
  state = next;
  renderAll(state);
}

async function checkHealth() {
  const indicator = document.getElementById("online-indicator");
  try {
    const r = await fetch("/health");
    const ok = r.ok && (await r.json()).status === "ok";
    indicator.textContent = ok ? "● ONLINE" : "○ DEGRADED";
    indicator.className = ok ? "on" : "off";
  } catch {
    indicator.textContent = "○ OFFLINE";
    indicator.className = "off";
  }
  document.getElementById("repo-count").textContent = String(REPOS.length).padStart(2, "0");
  document.getElementById("chunk-count").textContent = REPOS.reduce((a, r) => a + (r.chunks || 0), 0);
}

async function recall(query) {
  const input = document.getElementById("cmd-input");
  const send = document.getElementById("cmd-send");
  input.value = "";
  send.disabled = true;
  document.getElementById("session-id").textContent = "ACTIVE";

  // Reset to a fresh turn but keep the question visible.
  setState({ ...reduce(state, { event: "start", data: { conversation_id: conversationId } }), query });

  try {
    const resp = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: query, conversation_id: conversationId }),
    });
    if (!resp.ok) {
      setState({ ...reduce(state, { event: "error", data: { message: `server error (${resp.status})` } }), query });
      return;  // the finally block still re-enables the input
    }
    for await (const ev of streamSSE(resp)) {
      if (ev.event === "start" && ev.data?.conversation_id) {
        conversationId = ev.data.conversation_id;
      }
      setState({ ...reduce(state, ev), query });
    }
  } catch (err) {
    setState({ ...reduce(state, { event: "error", data: { message: String(err) } }), query });
  } finally {
    send.disabled = false;
    input.focus();
  }
}

function wire() {
  document.getElementById("cmd-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = document.getElementById("cmd-input").value.trim();
    if (q) recall(q);
  });

  // Click an example query in the empty state, or a [n] citation badge.
  document.getElementById("recall").addEventListener("click", (e) => {
    const ex = e.target.closest(".ex");
    if (ex) recall(ex.textContent.replace(/^›\s*/, "").trim());
    const cite = e.target.closest(".cite");
    if (cite) setState({ ...lockSource(state, Number(cite.dataset.n)), query: state.query });
  });

  document.getElementById("cmd-input").focus();
}

checkHealth();
renderAll(state);
wire();
