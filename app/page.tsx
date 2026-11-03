import {Suspense} from 'react';
import {Workspace} from '../ui/application/Workspace';

export default function Page() {
  return <Suspense fallback={<main className="boot" role="status">Opening your workspace…</main>}><Workspace /></Suspense>;
}
