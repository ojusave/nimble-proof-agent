'use client';
import {memo, useState} from 'react';
import {ArrowUpRight, Check, ChevronDown, FileSearch, ListTree} from 'lucide-react';
import type {Job, Citation} from '../core/types';
import {claimLabel} from '../core/session';
import {Badge, SourceLink, sourceHost} from './shared';

function Citations({sources}: {sources: Citation[]}) {
  return <div className="citations">{sources.filter(Boolean).map((source, index) => <div key={index}>
    {source.url && <SourceLink url={source.url}>{source.title || sourceHost(source.url)}</SourceLink>}
    {Array.isArray(source.excerpts) && source.excerpts.map((quote, n) => <blockquote key={n}>{quote}</blockquote>)}
  </div>)}</div>;
}

export const JobCard = memo(function JobCard({job, review, demo, onTrace}: {job: Job; review: boolean; demo: boolean; onTrace(url: string): void}) {
  const [open, setOpen] = useState(false);
  const trust = job.research?.trust;
  const claims = Array.isArray(trust?.claims) ? trust.claims.filter(Boolean) : [];
  return <article className={'job-card' + (review ? ' needs-review' : '')} data-job-id={job.id}>
    <div className="job-heading">
      <div className={'company-mark tone-' + job.company.length % 4} aria-hidden="true">{job.company[0]}</div>
      <div className="job-identity"><p className="company-name">{job.company}</p><h3>{job.title}</h3><p className="job-location">{job.location || 'Location not stated'}</p></div>
      {!review && <span className="match-mark" title="Supporting quotations checked"><Check size={16} aria-hidden="true"/><span className="sr-only">Supporting quotations checked</span></span>}
    </div>
    <p className="job-fit">{job.strengths[0]?.reason || job.summary}</p>
    {review && <div className="review-reason"><span className="status-dot amber"/>Needs confirmation: {(job.unknown_requirements || ['Application availability']).join(' · ')}</div>}
    <div className="job-actions">
      <button className="text-button" aria-expanded={open} aria-controls={'evidence-' + job.id} onClick={() => setOpen(value => !value)}><FileSearch size={15}/>{open ? 'Hide evidence' : 'Inspect evidence'}<ChevronDown size={14} className={open ? 'rotate' : ''}/></button>
      {demo ? <Badge>Fictional listing</Badge> : <SourceLink url={job.url}>View opening</SourceLink>}
    </div>
    {open && <div id={'evidence-' + job.id} className="job-evidence">
      <section><h4>Why it may fit</h4>{job.strengths.map((strength, index) => <div className="strength" key={index}>
        <p>{strength.reason}</p><div className="quote-pair"><div><span className="eyebrow">Your résumé</span><blockquote>{strength.resume_quote}</blockquote></div><div><span className="eyebrow">Job listing</span><blockquote>{strength.job_quote}</blockquote></div></div>
      </div>)}</section>
      {!!job.checks.length && <section><h4>Your requirements</h4>{job.checks.map(check => <div className="requirement" key={check.id}>
        <div><Badge tone={check.status === 'met' ? 'green' : 'amber'}>{check.status === 'met' ? 'Quote checked' : check.status === 'conflict' ? 'Conflict' : 'Not confirmed'}</Badge><strong>{check.requirement}</strong></div>
        {check.evidence && <blockquote>{check.evidence}</blockquote>}
      </div>)}</section>}
      {!!job.gaps.length && <section><h4>Potential gaps</h4><ul className="gap-list">{job.gaps.map((gap, index) => <li key={index}>{gap}</li>)}</ul></section>}
      <section><h4>Application availability</h4>{job.open_evidence ? <blockquote>{job.open_evidence}</blockquote> : <p className="muted">No application instruction could be confirmed against the captured text.</p>}
        <p className="evidence-note">Quotes show the source of a claim. They do not guarantee the role is open or the recommendation is right.</p>
        {job.checked_at && <p className="timestamp">Checked {new Date(job.checked_at).toLocaleString()}</p>}
      </section>
      {job.evidence && <details className="evidence-fold"><summary>Captured listing passages <span>{job.evidence.passages.length}</span></summary>
        <p className="muted">{job.evidence.selected_characters.toLocaleString()} characters selected from {job.evidence.source_characters.toLocaleString()}.</p>
        {job.evidence.scan_limited && <p className="notice">Only the first {job.evidence.scanned_characters.toLocaleString()} characters were scanned.</p>}
        {job.evidence.passages.map(passage => <div className="passage" key={passage.id}><small>Source characters {passage.start}–{passage.end}</small><blockquote>{passage.text}</blockquote></div>)}
      </details>}
      {job.research?.run_id && <section className="research-sources"><div className="section-heading"><h4>Research sources</h4>{trust?.confidence != null && <Badge>Provider: {trust.confidence}</Badge>}</div>
        <p className="evidence-note">Provider-reported confidence is separate from the app’s quote checks.</p>
        <Citations sources={Array.isArray(trust?.sources) ? trust.sources : []}/>
        {!!claims.length && <details className="evidence-fold"><summary>Evidence by claim <span>{claims.length}</span></summary>
          {claims.map((claim, index) => <details className="claim" key={index}><summary>{claimLabel(claim.path, job.checks)}<Badge tone={claim.confidence === 'low' ? 'amber' : 'neutral'}>{claim.confidence || 'Unrated'}</Badge></summary>
            {claim.reasoning && <p>{claim.reasoning}</p>}<Citations sources={Array.isArray(claim.citations) ? claim.citations : []}/>
            {!claim.citations?.length && <p className="muted">No source citation was returned for this claim.</p>}
          </details>)}
        </details>}
        {!claims.length && !trust?.sources?.length && <p className="muted">The provider returned no source citations.</p>}
      </section>}
      <button className="trace-link" onClick={() => onTrace(job.url)}><ListTree size={15}/>Follow this opening in the activity trace<ArrowUpRight size={14}/></button>
    </div>}
  </article>;
});
