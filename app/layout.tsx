import type {Metadata} from 'next';
import '../ui/styles.css';

export const metadata: Metadata = {title: 'Proof — jobs with evidence', description: 'Find and inspect a résumé-based job shortlist.'};
export default function Layout({children}: {children: React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
