import {ExternalLink} from 'lucide-react';
import type {ReactNode} from 'react';

export function SourceLink({url, children}: {url: string; children: ReactNode}) {
  try {if (new URL(url).protocol !== 'https:') return <span>{children}</span>;} catch {return <span>{children}</span>;}
  return <a className="source-link" href={url} target="_blank" rel="noopener noreferrer">{children}<ExternalLink size={12} aria-hidden="true" /></a>;
}
export function sourceHost(url: string) {
  try {return new URL(url).hostname;} catch {return 'Source';}
}
export function Badge({children, tone = 'neutral'}: {children: ReactNode; tone?: string}) {
  return <span className={'badge ' + tone}>{children}</span>;
}
export function elapsedLabel(start: string, end: string | number = Date.now()) {
  const seconds = Math.max(0, Math.floor((new Date(end).getTime() - new Date(start).getTime()) / 1000));
  return Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
}
