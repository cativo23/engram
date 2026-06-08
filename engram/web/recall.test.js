import { describe, it, expect } from "vitest";
import { initialState, reduce, fireRepos, lockSource } from "./recall.js";

const REPOS = [
  { name: "nightwire", lang: "CSS", chunks: 142 },
  { name: "llm-from-scratch", lang: "PY", chunks: 96 },
  { name: "engram", lang: "PY", chunks: 51 },
];

function apply(events) {
  return events.reduce(reduce, initialState(REPOS));
}

describe("fireRepos", () => {
  it("fires repos present in citations (matched by basename), max similarity wins", () => {
    const cites = [
      { repo: "cativo23/nightwire", similarity: 0.6 },
      { repo: "cativo23/nightwire", similarity: 0.88 },
      { repo: "cativo23/engram", similarity: 0.4 },
    ];
    const repos = fireRepos(REPOS.map(r => ({ ...r, fired: false, score: null })), cites);
    const byName = Object.fromEntries(repos.map(r => [r.name, r]));
    expect(byName["nightwire"].fired).toBe(true);
    expect(byName["nightwire"].score).toBeCloseTo(0.88);
    expect(byName["engram"].fired).toBe(true);
    expect(byName["llm-from-scratch"].fired).toBe(false);
    expect(byName["llm-from-scratch"].score).toBeNull();
  });
});

describe("reduce", () => {
  it("start resets answer/citations and clears fired repos", () => {
    const s = apply([
      { event: "citations", data: { citations: [{ n: 1, repo: "cativo23/nightwire", similarity: 0.8 }] } },
      { event: "token", data: { text: "old" } },
      { event: "start", data: { conversation_id: "c" } },
    ]);
    expect(s.answer).toBe("");
    expect(s.citations).toEqual([]);
    expect(s.repos.every(r => !r.fired)).toBe(true);
    expect(s.status).toBe("searching");
  });

  it("records the retrieval trace from tool events", () => {
    const s = apply([{ event: "tool", data: { name: "search_code", query: "loop" } }]);
    expect(s.trace).toEqual([{ name: "search_code", query: "loop" }]);
  });

  it("accumulates citations, fires repos, and locks onto the first citation", () => {
    const s = apply([
      { event: "citations", data: { citations: [
        { n: 1, repo: "cativo23/nightwire", path: "modes.css", similarity: 0.88 },
        { n: 2, repo: "cativo23/engram", path: "agent.py", similarity: 0.5 },
      ] } },
    ]);
    expect(s.citations).toHaveLength(2);
    expect(s.sourceLock.n).toBe(1);
    expect(s.repos.find(r => r.name === "nightwire").fired).toBe(true);
  });

  it("appends streamed tokens into the answer", () => {
    const s = apply([
      { event: "token", data: { text: "Hello " } },
      { event: "token", data: { text: "world" } },
    ]);
    expect(s.answer).toBe("Hello world");
    expect(s.status).toBe("streaming");
  });

  it("an empty citations batch leaves sourceLock null", () => {
    const s = apply([{ event: "citations", data: { citations: [] } }]);
    expect(s.sourceLock).toBeNull();
    expect(s.citations).toEqual([]);
  });

  it("done sets terminal status", () => {
    const s = apply([{ event: "done", data: {} }]);
    expect(s.status).toBe("done");
  });

  it("done after error keeps the error status (backend emits error then done)", () => {
    const s = apply([
      { event: "error", data: { message: "boom" } },
      { event: "done", data: {} },
    ]);
    expect(s.status).toBe("error");
    expect(s.error).toBe("boom");
  });
});

describe("lockSource", () => {
  it("locks SOURCE LOCK onto a citation by its [n]", () => {
    const base = apply([
      { event: "citations", data: { citations: [
        { n: 1, repo: "cativo23/nightwire", similarity: 0.88 },
        { n: 2, repo: "cativo23/engram", similarity: 0.5 },
      ] } },
    ]);
    expect(lockSource(base, 2).sourceLock.n).toBe(2);
    expect(lockSource(base, 99).sourceLock.n).toBe(1); // unknown n -> unchanged
    expect(lockSource(base, 99)).toBe(base); // unknown n -> identical ref, no re-render
  });
});
