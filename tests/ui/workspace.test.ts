import {describe, expect, it} from 'vitest';
import {proxy} from '../../proxy';
import {NextRequest} from 'next/server';
import {workspaceCookie, workspaceId} from '../../server/workspace';

describe('automatic browser workspace', () => {
  it('opens directly and creates a private cookie on the first request', () => {
    const response = proxy(new NextRequest('http://localhost:8765/'));
    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
    const cookie = response.headers.get('set-cookie')!;
    expect(cookie).toContain('HttpOnly');
    expect(cookie).toContain('SameSite=strict');
    const incoming = response.headers.get('x-middleware-request-cookie')!;
    expect(workspaceId(new Request('http://localhost', {headers: {cookie: incoming}}))).toMatch(/^[a-f0-9]{64}$/);
  });
  it('keeps reloads in the same workspace and ignores caller-supplied scope headers', () => {
    const cookie = `${workspaceCookie}=${'a'.repeat(64)}`;
    const request = new NextRequest('http://localhost:8765/', {headers: {cookie}});
    expect(proxy(request).headers.get('set-cookie')).toBeNull();
    expect(workspaceId(request)).toBe(workspaceId(new Request('http://localhost', {
      headers: {cookie, 'x-proof-workspace': 'forged'}})));
    expect(workspaceId(request)).not.toBe('a'.repeat(64));
    expect(workspaceId(request)).not.toBe(workspaceId(new Request('http://localhost', {
      headers: {cookie: `${workspaceCookie}=${'b'.repeat(64)}`}})));
  });
  it('replaces malformed cookies and never falls back to the legacy workspace', () => {
    const request = new NextRequest('http://localhost:8765/api/backend/resumes', {
      headers: {cookie: `${workspaceCookie}=local`}});
    expect(proxy(request).headers.get('set-cookie')).toContain(workspaceCookie + '=');
    expect(() => workspaceId(request)).toThrow('workspace is missing');
  });
});
