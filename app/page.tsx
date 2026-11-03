import {Suspense} from 'react';
import {Workspace} from '../ui/application/Workspace';
import {Providers} from '../ui/composition';

export const dynamic = 'force-dynamic';
export default function Page() {
  return <Providers><Suspense fallback={<main className="boot" role="status">Opening your workspace…</main>}><Workspace canSignOut={!!process.env.PROOF_ACCESS_PASSWORD} /></Suspense></Providers>;
}
