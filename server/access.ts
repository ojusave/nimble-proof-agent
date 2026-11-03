const localHosts = ['127.0.0.1', 'localhost', '[::1]'];

/** Public application with same-origin requests; browser data is scoped separately. */
export function requestAccess(request: Request): Response | null {
  const publicUrl = process.env.PROOF_PUBLIC_URL || process.env.RENDER_EXTERNAL_URL;
  const hosted = !!publicUrl || process.env.RENDER === 'true';
  try {
    const url = new URL(request.url);
    const host = request.headers.get('host') || url.host;
    const address = new URL(`${url.protocol}//${host}`);
    const expected = publicUrl ? new URL(publicUrl) : null;
    const origin = request.headers.get('origin');
    const allowed = expected ? host === expected.host : localHosts.includes(address.hostname);
    if (!allowed || address.username || address.password || (origin && origin !== (expected?.origin || address.origin)))
      return new Response('Same origin required.', {status: 403});
  } catch {
    return new Response('Invalid origin.', {status: 403});
  }
  if (hosted && !publicUrl) return new Response('Public origin is not configured.', {status: 503});
  return null;
}
