import {createHash, randomBytes} from 'node:crypto';

// A browser capability, not an account or login. Keep the token out of URLs and JS.
export const workspaceCookie = 'proof_workspace';
export const workspaceHeader = 'x-proof-workspace';
export const workspaceLifetime = 60 * 60 * 24 * 30;

export function workspaceToken(request: Request): string | undefined {
  const token = (request.headers.get('cookie') || '').split(';').map(value => value.trim())
    .find(value => value.startsWith(workspaceCookie + '='))?.slice(workspaceCookie.length + 1);
  return token && /^[a-f0-9]{64}$/.test(token) ? token : undefined;
}

export const newWorkspaceToken = () => randomBytes(32).toString('hex');

export function workspaceId(request: Request): string {
  const token = workspaceToken(request);
  if (!token) throw new Error('Browser workspace is missing. Reload the page.');
  return createHash('sha256').update('proof-workspace:' + token).digest('hex');
}
