import {NextRequest, NextResponse} from 'next/server';
import {requestAccess} from './server/access';
import {newWorkspaceToken, workspaceCookie, workspaceLifetime, workspaceToken} from './server/workspace';

export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname === '/api/health' && request.method === 'GET') return NextResponse.next();
  const denied = requestAccess(request);
  if (denied) return denied;
  if (workspaceToken(request)) return NextResponse.next();
  const token = newWorkspaceToken();
  const headers = new Headers(request.headers);
  const cookies = (headers.get('cookie') || '').split(';').map(value => value.trim())
    .filter(value => value && !value.startsWith(workspaceCookie + '='));
  headers.set('cookie', [...cookies, `${workspaceCookie}=${token}`].join('; '));
  const response = NextResponse.next({request: {headers}});
  const publicUrl = process.env.PROOF_PUBLIC_URL || process.env.RENDER_EXTERNAL_URL;
  response.cookies.set(workspaceCookie, token, {httpOnly: true, sameSite: 'strict', path: '/',
    secure: publicUrl ? new URL(publicUrl).protocol === 'https:' : request.nextUrl.protocol === 'https:',
    maxAge: workspaceLifetime});
  response.headers.set('Cache-Control', 'no-store');
  return response;
}

export const config = {matcher: ['/((?!_next/static|_next/image|icon.svg).*)']};
