import {describe, expect, it} from 'vitest';
import {createSession, safeReturnPath, validSession} from '../../server/session';

describe('shared workspace sessions', () => {
  const secret = 'test-only-secret-with-at-least-32-characters';
  it('rejects expired, tampered, and password-rotated sessions', () => {
    const now = Date.now(), session = createSession(secret, now);
    expect(validSession(session, secret, now + 1000)).toBe(true);
    expect(validSession(session, secret, now + 8 * 3600 * 1000)).toBe(false);
    expect(validSession(session + '0', secret, now)).toBe(false);
    expect(validSession(session, 'different-password', now)).toBe(false);
  });
  it('returns only to the workspace or a saved run, never an external destination', () => {
    const run = '/?run=' + 'a'.repeat(32);
    expect(safeReturnPath(run)).toBe(run);
    for (const path of ['//evil.example', 'https://evil.example', '/\\evil.example', '/sign-in', '/api/session'])
      expect(safeReturnPath(path)).toBe('/');
  });
});
