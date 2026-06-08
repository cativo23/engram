// Pure state reducers that turn the SSE event log into console view-state.
// No DOM here — this is the unit-tested brain of the recall console.

export function initialState(repos) {
  return {
    status: "standby", // standby | searching | streaming | done | error
    repos: repos.map((r) => ({ ...r, fired: false, score: null })),
    trace: [], // [{ name, query }]
    citations: [], // [{ n, repo, path, line_start, line_end, similarity, snippet, github_url }]
    answer: "",
    sourceLock: null,
    error: null,
  };
}

// A repo "fires" when it appears in the citations; its score is the max similarity
// of its hits. Citations carry "owner/name"; INDEX CORE lists bare names — match on basename.
export function fireRepos(repos, citations) {
  const best = {};
  for (const c of citations) {
    // Match citations (owner/name) against the INDEX CORE list by basename.
    const name = c.repo.includes("/") ? c.repo.split("/").pop() : c.repo;
    best[name] = Math.max(best[name] ?? 0, c.similarity ?? 0);
  }
  return repos.map((r) =>
    r.name in best
      ? { ...r, fired: true, score: best[r.name] }
      : { ...r, fired: false, score: null }
  );
}

export function reduce(state, ev) {
  switch (ev.event) {
    case "start":
      return {
        ...state,
        status: "searching",
        answer: "",
        citations: [],
        trace: [],
        sourceLock: null,
        error: null,
        repos: state.repos.map((r) => ({ ...r, fired: false, score: null })),
      };
    case "tool":
      return {
        ...state,
        status: "searching",
        trace: [...state.trace, { name: ev.data.name, query: ev.data.query }],
      };
    case "citations": {
      const citations = [...state.citations, ...ev.data.citations];
      return {
        ...state,
        citations,
        repos: fireRepos(state.repos, citations),
        sourceLock: state.sourceLock || citations[0] || null,
      };
    }
    case "token":
      return { ...state, status: "streaming", answer: state.answer + ev.data.text };
    case "done":
      // The backend emits `error` then `done`; `done` means "stream closed" and
      // must not overwrite an error that already occurred.
      return { ...state, status: state.status === "error" ? "error" : "done" };
    case "error":
      return { ...state, status: "error", error: ev.data?.message ?? "unknown error" };
    default:
      return state;
  }
}

// Click a [n] badge -> show that citation in SOURCE LOCK. Unknown n -> unchanged.
export function lockSource(state, n) {
  const c = state.citations.find((x) => x.n === n);
  return c ? { ...state, sourceLock: c } : state;
}
