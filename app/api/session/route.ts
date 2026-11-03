import {requestAccess} from '../../../server/access';
import {limitedBody} from '../../../server/body';
import {createSession, safeReturnPath, sessionCookie, sessionLifetime} from '../../../server/session';

export const runtime = 'nodejs';
export async function POST(request: Request) {
  const denied = requestAccess(request);
  if (denied && denied.status !== 401) return denied;
  // Forms require an Origin even if a regular read-only request does not.
  if (!request.headers.get('origin')) return new Response('Origin required.', {status: 403});
  let form: URLSearchParams;
  try { form = new URLSearchParams(new TextDecoder().decode(await limitedBody(request, 8192))); }
  catch { return new Response('Invalid sign-in request.', {status: 400}); }
  if (form.get('action') === 'sign-out') return new Response(null, {status: 303, headers: {
    Location: '/sign-in', 'Set-Cookie': `${sessionCookie}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`, 'Cache-Control': 'no-store',
  }});
  const password = form.get('password') || '';
  const headers = new Headers(request.headers);
  headers.delete('cookie');
  headers.set('authorization', 'Basic ' + Buffer.from(`${process.env.PROOF_ACCESS_USER || 'proof'}:${password}`).toString('base64'));
  const result = requestAccess(new Request(request.url, {headers}));
  const next = safeReturnPath(form.get('next') || '/');
  if (result || !process.env.PROOF_ACCESS_PASSWORD) {
    await new Promise(resolve => setTimeout(resolve, 750));
    return new Response(null, {status: 303, headers: {Location: '/sign-in?error=1&next=' + encodeURIComponent(next), 'Cache-Control': 'no-store'}});
  }
  const token = createSession(process.env.PROOF_ACCESS_PASSWORD);
  return new Response(null, {status: 303, headers: {
    Location: next, 'Set-Cookie': `${sessionCookie}=${token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${sessionLifetime}`, 'Cache-Control': 'no-store',
  }});
}
