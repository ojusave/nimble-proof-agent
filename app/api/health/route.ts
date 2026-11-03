import {backendUrl} from '../../../server/backend';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export async function GET() {
  try {
    const response = await fetch(backendUrl + '/api/health', {cache: 'no-store', signal: AbortSignal.timeout(2500)});
    return Response.json({status: response.ok ? 'ok' : 'unavailable'}, {status: response.ok ? 200 : 503});
  } catch {
    return Response.json({status: 'unavailable'}, {status: 503});
  }
}
