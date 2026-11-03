import { backendUrl } from '../../../../server/backend';
import {requestAccess} from '../../../../server/access';
import {limitedBody} from '../../../../server/body';

export const runtime = 'nodejs';
async function proxy(request: Request, context: {params: Promise<{path: string[]}>}) {
  const denied = requestAccess(request); if (denied) return denied;
  const {path} = await context.params;
  if (!['config', 'resumes', 'searches', 'demo'].includes(path[0]) || path.some(p => p === '..' || p.includes('/')))
    return new Response('Not found.', {status: 404});
  const headers = new Headers();
  for (const name of ['content-type', 'last-event-id']) {
    const value = request.headers.get(name); if (value) headers.set(name, value);
  }
  try {
    const response = await fetch(backendUrl + '/api/' + path.map(encodeURIComponent).join('/'), {
      method: request.method, headers, cache: 'no-store', signal: request.signal,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : await limitedBody(request, path[0] === 'resumes' ? 4 * 1024 * 1024 : 64 * 1024),
    });
    const output = new Headers({'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'});
    for (const name of ['content-type', 'content-disposition']) {
      const value = response.headers.get(name); if (value) output.set(name, value);
    }
    return new Response(response.body, {status: response.status, headers: output});
  } catch (error) {
    if (error instanceof RangeError) return Response.json({detail: error.message}, {status: 413});
    return Response.json({detail: 'The search service is unavailable. Please reconnect shortly.'}, {status: 503});
  }
}
export {proxy as GET, proxy as POST, proxy as DELETE};
