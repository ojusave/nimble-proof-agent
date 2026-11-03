import {safeReturnPath} from '../../server/session';

export default async function SignIn({searchParams}: {searchParams: Promise<Record<string, string | string[] | undefined>>}) {
  const params = await searchParams;
  return <main className="sign-in-page">
    <a className="brand" href="/"><span className="brand-mark">p</span>proof</a>
    <div className="sign-in-card">
      <p className="eyebrow">YOUR WORKSPACE</p>
      <h1>Welcome back.</h1>
      <p>Enter your workspace password to continue.</p>
      <form action="/api/session" method="post">
        <input type="hidden" name="next" value={safeReturnPath(typeof params.next === 'string' ? params.next : '/')} />
        <label htmlFor="password">Workspace password</label>
        <input id="password" name="password" type="password" autoComplete="current-password" required autoFocus />
        {params.error && <p className="sign-in-error" role="alert">That password didn’t match. Please try again.</p>}
        <button className="primary-button" type="submit">Open workspace</button>
      </form>
    </div>
  </main>;
}
