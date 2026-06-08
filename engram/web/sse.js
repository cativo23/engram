// Server-Sent Events parsing for the Engram recall console.
//
// `parseSSE` is PURE: given the leftover buffer plus a new chunk of text, it
// returns the complete events it could parse and the (possibly incomplete)
// trailing frame to carry into the next call. This is the unit-tested core.
//
// `streamSSE` is the thin runtime wrapper around a fetch() ReadableStream.

export function parseSSE(chunkText, buffer) {
  buffer += chunkText;
  const frames = buffer.split("\n\n");
  const rest = frames.pop(); // last element is the incomplete tail (or "")
  const events = [];
  for (const frame of frames) {
    if (!frame.trim()) continue;
    let event = "message";
    let data = "";
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      // assumes one data: line per event (the backend emits compact single-line JSON); multi-line data: would need "\n" joins
      else if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    let parsed = null;
    try {
      parsed = data ? JSON.parse(data) : null;
    } catch {
      parsed = null;
    }
    events.push({ event, data: parsed });
  }
  return { events, rest };
}

// Async generator over a fetch Response body. Usage:
//   for await (const { event, data } of streamSSE(response)) { ... }
export async function* streamSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      buffer += decoder.decode(); // flush any held partial multibyte char
      break;
    }
    const { events, rest } = parseSSE(decoder.decode(value, { stream: true }), buffer);
    buffer = rest;
    for (const ev of events) yield ev;
  }
}
