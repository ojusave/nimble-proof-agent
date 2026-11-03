import {ArrowRight, CircleHelp, LoaderCircle} from 'lucide-react';
import type {Candidate} from '../core/types';
import {SourceLink,sourceHost} from './shared';

export function CandidateCard({candidate,active,onTrace}: {candidate: Candidate; active: boolean; onTrace(url: string): void}) {
  const checking=active && candidate.status !== 'unverified';
  const label=!checking ? 'Not verified' : candidate.status === 'reading' ? 'Reading page' : candidate.status === 'researching' ? 'Researching fit' : 'Found · waiting to check';
  return <article className="job-card candidate-card" data-candidate-id={candidate.id}>
    <p className="company-name">{sourceHost(candidate.url)}</p><h3>{candidate.title}</h3>
    <p className="candidate-state">{checking ? <LoaderCircle size={14} className="spin"/> : <CircleHelp size={14}/>} {label}</p>
    <p className="candidate-note">{candidate.reason || (checking ? 'This is a discovered page. Suitability and availability are still being checked.' : 'No verified assessment was received. This is not a rejection of your fit.')}</p>
    <div className="job-actions"><SourceLink url={candidate.url}>View source</SourceLink><button className="text-button" onClick={() => onTrace(candidate.url)}>View trace<ArrowRight size={13}/></button></div>
  </article>;
}
