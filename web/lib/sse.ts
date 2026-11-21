// Minimal text/event-stream reader for the engine's /v1/runs stream.
// Handles events split across network chunks and CRLF line endings.

type SSEEvent = { event: string; data: string };

export async function* parseSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<SSEEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buf += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      buf = buf.replace(/\r\n/g, "\n");
      let cut: number;
      while ((cut = buf.indexOf("\n\n")) !== -1) {
        const block = buf.slice(0, cut);
        buf = buf.slice(cut + 2);
        const ev = parseBlock(block);
        if (ev) yield ev;
      }
      if (done) {
        const ev = parseBlock(buf);
        if (ev) yield ev;
        return;
      }
    }
  } finally {
    void reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

function parseBlock(block: string): SSEEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const i = line.indexOf(":");
    const field = i === -1 ? line : line.slice(0, i);
    const value = i === -1 ? "" : line.slice(i + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length ? { event, data: data.join("\n") } : null;
}

/** Newline-delimited JSON reader for /api/ask. */
export async function* parseNDJSON<T>(body: ReadableStream<Uint8Array>): AsyncGenerator<T> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buf += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let cut: number;
      while ((cut = buf.indexOf("\n")) !== -1) {
        const line = buf.slice(0, cut).trim();
        buf = buf.slice(cut + 1);
        if (line) yield JSON.parse(line) as T;
      }
      if (done) {
        if (buf.trim()) yield JSON.parse(buf) as T;
        return;
      }
    }
  } finally {
    void reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
