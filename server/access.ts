import {createHash, timingSafeEqual} from 'node:crypto';

const localHosts = ['127.0.0.1', 'localhost', '[::1]'];

function sameSecret(actual: string, expected: string): boolean {
  const digest = (value: string) => createHash('sha256').update(value).digest();
  return timingSafeEqual(digest(actual), digest(expected));
}

/** One shared workspace. Replace this adapter with identity/tenant auth to offer accounts. */
export function requestAccess(request: Request): Response | null {
  const password = process.env.PROOF_ACCESS_PASSWORD;
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
  // Fail closed when hosted configuration is missing, including forged loopback Hosts.
  if (hosted && (!publicUrl || !password || password.length < 24))
    return new Response('Workspace access is not configured.', {status: 503});
  if (!password) return null;
  const header = request.headers.get('authorization') || '';
  const credential = header.startsWith('Basic ') ? Buffer.from(header.slice(6), 'base64').toString('utf8') : '';
  if (sameSecret(credential, `${process.env.PROOF_ACCESS_USER || 'proof'}:${password}`)) return null;
  return new Response('Sign in to the Proof workspace.', {
    status: 401,
    headers: {'WWW-Authenticate': 'Basic realm="Proof", charset="UTF-8"', 'Cache-Control': 'no-store'},
  });
}
