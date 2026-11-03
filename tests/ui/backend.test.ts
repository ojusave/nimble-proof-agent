import {afterEach, describe, expect, it, vi} from 'vitest';
import {requestAccess} from '../../server/access';
import {limitedBody} from '../../server/body';

afterEach(() => vi.unstubAllEnvs());
const localRequest = (request: Request) => requestAccess(request) === null;

describe('local request boundary', () => {
  it('accepts the real loopback host when Next normalizes the URL', () => {
    expect(localRequest(new Request('http://localhost:8765/api/backend/demo', {
      headers: {host: '127.0.0.1:8765', origin: 'http://127.0.0.1:8765'},
    }))).toBe(true);
  });
  it('rejects cross-origin requests and untrusted hosts', () => {
    const cases: Record<string, string>[] = [
      {host: '127.0.0.1:8765', origin: 'https://example.com'},
      {host: 'example.com', origin: 'http://example.com'},
      {host: 'example.com', 'x-forwarded-host': 'localhost:8765'},
      {host: 'localhost:8765', origin: 'http://localhost:8888'},
    ];
    for (const headers of cases) expect(localRequest(new Request('http://localhost:8765', {headers}))).toBe(false);
  });
});

describe('hosted workspace boundary', () => {
  const configure = () => {
    vi.stubEnv('RENDER', 'true');
    vi.stubEnv('RENDER_EXTERNAL_URL', 'https://proof.onrender.com');
  };
  const request = (headers: Record<string, string> = {}) => new Request('http://localhost:10000/api/backend/searches', {
    headers: {host: 'proof.onrender.com', ...headers},
  });
  it('opens without a password, including deployments with old credentials configured', () => {
    configure();
    expect(requestAccess(request())).toBeNull();
    vi.stubEnv('PROOF_ACCESS_PASSWORD', 'obsolete-configuration');
    expect(requestAccess(request({origin: 'https://proof.onrender.com'}))).toBeNull();
  });
  it('still rejects cross-origin requests and forged loopback hosts', () => {
    configure();
    expect(requestAccess(request({origin: 'https://attacker.example'}))?.status).toBe(403);
    expect(requestAccess(request({host: '127.0.0.1:10000'}))?.status).toBe(403);
  });
  it('requires the hosted public origin', () => {
    configure();
    vi.stubEnv('RENDER_EXTERNAL_URL', '');
    expect(requestAccess(request({host: 'localhost:10000'}))?.status).toBe(503);
  });
  it('rejects oversized chunked payloads without relying on content-length', async () => {
    await expect(limitedBody(new Request('http://localhost', {method: 'POST', body: '12345'}), 4)).rejects.toThrow('Request too large');
    expect(new TextDecoder().decode(await limitedBody(new Request('http://localhost', {method: 'POST', body: '1234'}), 4))).toBe('1234');
  });
});
