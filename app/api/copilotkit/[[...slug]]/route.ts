import { copilotHandler } from '../../../../server/copilot';
import {requestAccess} from '../../../../server/access';
import {limitedBody} from '../../../../server/body';

export const runtime = 'nodejs';
const handler = async (request: Request) => {
  const denied = requestAccess(request); if (denied) return denied;
  try {
    if (!['GET', 'HEAD'].includes(request.method)) {
      const body = await limitedBody(request, 256 * 1024);
      request = new Request(request.url, {method: request.method, headers: request.headers, body, signal: request.signal});
    }
    return copilotHandler(request);
  } catch (error) {
    if (error instanceof RangeError) return new Response(error.message, {status: 413});
    throw error;
  }
};
export {handler as GET, handler as POST, handler as PATCH, handler as DELETE};
