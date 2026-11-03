import {createHmac, timingSafeEqual, randomBytes} from 'node:crypto';

export const sessionCookie = '__Host-proof_session';
export const sessionLifetime = 8 * 60 * 60;
const signature = (value: string, secret: string) => createHmac('sha256', secret).update('proof-session:' + value).digest('hex');

export function createSession(secret: string, now = Date.now()): string {
  const value = `${Math.floor(now / 1000) + sessionLifetime}.${randomBytes(16).toString('hex')}`;
  return value + '.' + signature(value, secret);
}

export function validSession(token: string, secret: string, now = Date.now()): boolean {
  const match = /^(\d{10})\.([a-f0-9]{32})\.([a-f0-9]{64})$/.exec(token);
  if (!match) return false;
  const expires = Number(match[1]), current = Math.floor(now / 1000);
  if (expires <= current || expires > current + sessionLifetime) return false;
  return timingSafeEqual(Buffer.from(match[3], 'hex'), Buffer.from(signature(`${match[1]}.${match[2]}`, secret), 'hex'));
}

export function sessionFromRequest(request: Request): string {
  return (request.headers.get('cookie') || '').split(';').map(value => value.trim())
    .find(value => value.startsWith(sessionCookie + '='))?.slice(sessionCookie.length + 1) || '';
}

export function safeReturnPath(value: string): string {
  return /^\/\?run=[a-f0-9]{32}$/.test(value) ? value : '/';
}
