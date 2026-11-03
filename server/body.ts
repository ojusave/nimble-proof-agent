/** Bound both declared and chunked bodies before forwarding to the internal API. */
export async function limitedBody(request: Request, limit: number): Promise<ArrayBuffer> {
  if (Number(request.headers.get('content-length')) > limit) throw new RangeError('Request too large.');
  const reader = request.body?.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  if (reader) {
    try {
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > limit) { await reader.cancel(); throw new RangeError('Request too large.'); }
        chunks.push(value);
      }
    } finally { reader.releaseLock(); }
  }
  const result = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
  return result.buffer;
}
