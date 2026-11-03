import type {Metadata} from 'next';
import {Providers} from '../ui/composition';
import '../ui/styles.css';

export const metadata: Metadata = {title: 'Proof — jobs with evidence', description: 'Find and inspect a résumé-based job shortlist.'};
export default function Layout({children}: {children: React.ReactNode}) {
  return <html lang="en"><body><Providers>{children}</Providers></body></html>;
}
