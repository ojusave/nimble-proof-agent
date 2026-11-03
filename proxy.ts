import {NextRequest, NextResponse} from 'next/server';
import {requestAccess} from './server/access';

export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname === '/api/health' && request.method === 'GET') return NextResponse.next();
  return requestAccess(request) || NextResponse.next();
}

export const config = {matcher: '/:path*'};
