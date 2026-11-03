import {NextRequest, NextResponse} from 'next/server';
import {requestAccess} from './server/access';

export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname === '/api/health' && request.method === 'GET') return NextResponse.next();
  const denied = requestAccess(request);
  if (!denied) return NextResponse.next();
  if (denied.status !== 401) return denied;
  const path = request.nextUrl.pathname;
  if (path === '/sign-in' || path === '/api/session' || path.startsWith('/_next/static/') || path === '/icon.svg')
    return NextResponse.next();
  if (path.startsWith('/api/')) return denied;
  const signIn = new URL('/sign-in', process.env.PROOF_PUBLIC_URL || process.env.RENDER_EXTERNAL_URL || request.url);
  signIn.searchParams.set('next', path + request.nextUrl.search);
  return NextResponse.redirect(signIn);
}

export const config = {matcher: '/:path*'};
