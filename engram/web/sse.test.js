import { describe, it, expect } from "vitest";
import { parseSSE } from "./sse.js";

describe("parseSSE", () => {
  it("parses complete frames and JSON-decodes data", () => {
    const text =
      'event: start\ndata: {"conversation_id":"abc"}\n\n' +
      'event: token\ndata: {"text":"hi"}\n\n';
    const { events, rest } = parseSSE(text, "");
    expect(rest).toBe("");
    expect(events).toEqual([
      { event: "start", data: { conversation_id: "abc" } },
      { event: "token", data: { text: "hi" } },
    ]);
  });

  it("holds back an incomplete trailing frame in `rest`", () => {
    const { events, rest } = parseSSE('event: token\ndata: {"text":"a"}\n\nevent: tok', "");
    expect(events).toHaveLength(1);
    expect(rest).toBe("event: tok");
  });

  it("stitches a frame split across two chunks via the buffer", () => {
    const first = parseSSE('event: token\nda', "");
    expect(first.events).toHaveLength(0);
    const second = parseSSE('ta: {"text":"x"}\n\n', first.rest);
    expect(second.events).toEqual([{ event: "token", data: { text: "x" } }]);
  });

  it("defaults event name to 'message' and tolerates bad JSON", () => {
    const { events } = parseSSE("data: not-json\n\n", "");
    expect(events).toEqual([{ event: "message", data: null }]);
  });
});
