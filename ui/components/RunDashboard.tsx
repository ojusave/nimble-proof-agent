'use client';
import {useEffect, useMemo, useRef, useState, type KeyboardEvent} from 'react';
import {Download, ListTree, LoaderCircle, RefreshCw, ArrowRight, CircleAlert, Check, Square} from 'lucide-react';
import {useQueryClient} from '@tanstack/react-query';
import {useSearchSession} from '../application/SessionContext';
import type {SearchRepository} from '../core/ports';
import {runView} from '../core/session';
import {CandidateCard} from './CandidateCard';
import {JobCard} from './JobCard';
import {TracePanel} from './TracePanel';
import {Badge, SourceLink, elapsedLabel} from './shared';

export function RunDashboard({repository, onEdit, onStatus}: {repository: SearchRepository; onEdit(): void; onStatus(active: boolean): void}) {
  const {run, events, connection, error, transport, reconnect} = useSearchSession();
  const view = useMemo(() => runView(run, events), [run, events]);
  const [tab, setTab] = useState<'matches' | 'review' | 'checking'>('matches');
  const [traceOpen, setTraceOpen] = useState(false);
  const [stopRequested, setStopRequested] = useState(false), [stopError, setStopError] = useState('');
  const stopLock = useRef(false);
  const [focus, setFocus] = useState<{url: string; version: number}>();
  const [now, setNow] = useState(Date.now());
  const queryClient = useQueryClient();
  const switched = useRef(false);
  const matchesTab = useRef<HTMLButtonElement>(null), reviewTab = useRef<HTMLButtonElement>(null), checkingTab = useRef<HTMLButtonElement>(null);
  useEffect(() => {onStatus(view.active);}, [view.active, onStatus]);
  useEffect(() => {
    if (!view.active) {void queryClient.invalidateQueries({queryKey: ['history']}); return;}
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [view.active, queryClient]);
  useEffect(() => {
    if (!switched.current) setTab(view.jobs.length ? 'matches' : view.unknowns.length ? 'review' : view.candidates.length ? 'checking' : 'matches');
  }, [view.active, view.jobs.length, view.unknowns.length, view.candidates.length]);
  const lastMeaningful = [...events].reverse().find(event => !['provider_status', 'provider_progress','node_started','node_completed','node_failed'].includes(event.type));
  const stopping = view.active && (stopRequested || run.status === 'stopping');
  const hasResults = view.jobs.length > 0 || view.unknowns.length > 0 || view.candidates.length > 0;
  async function stop() {
    if (stopLock.current || !view.active) return;
    stopLock.current = true; setStopRequested(true); setStopError('');
    try {await repository.stop(run.id);}
    catch (cause) {setStopRequested(false); setStopError(cause instanceof Error ? cause.message : 'Could not stop the search. Try again.');}
    finally {stopLock.current = false;}
  }
  const activeSteps: Record<string, string> = {resume: 'Reading your résumé', plan: 'Planning the search', search: 'Finding employer openings', extract: 'Reading listing pages', match: 'Researching and checking openings', verify: 'Checking supporting evidence', profile: 'Researching your public work', tailor: 'Preparing résumé suggestions', finish: 'Building your shortlist'};
  const title = stopping ? 'Stopping the search' : connection === 'reconnecting' ? 'Reconnecting to the search' : view.active ? activeSteps[lastMeaningful?.step || ''] || 'Starting your search' : run.status === 'complete' ? view.candidates.length ? 'Search finished · some pages unverified' : 'Search complete' : run.status === 'interrupted' ? 'Search interrupted' : 'Search stopped';
  const jobs = tab === 'review' ? view.unknowns : tab === 'matches' ? view.jobs : [];
  const follow = (url: string) => {setTraceOpen(true); setFocus(previous => ({url, version: (previous?.version || 0) + 1}));};
  const keyboardTab = (event: KeyboardEvent) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const tabs = ['matches','review',...(view.candidates.length ? ['checking'] : [])] as const;
    const index = tabs.indexOf(tab);
    const next = tabs[event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length-1 : (index+(event.key === 'ArrowRight' ? 1 : -1)+tabs.length)%tabs.length] as typeof tab;
    switched.current = true; setTab(next);
    ({matches:matchesTab,review:reviewTab,checking:checkingTab})[next].current?.focus();
  };
  return <section className="run-dashboard" aria-label="Search results">
    <div className={'run-status ' + (connection === 'reconnecting' || run.status === 'failed' || (!view.active && !!view.candidates.length) ? 'warning' : '')} role="status">
      <span className="run-status-icon">{view.active ? <LoaderCircle size={17} className="spin"/> : run.status === 'complete' && !view.candidates.length ? <Check size={17}/> : <CircleAlert size={17}/>}</span>
      <div><strong>{title}</strong>{stopping && <span>Waiting for in-flight requests. No new work will start.</span>}</div>
      <div className="run-status-meta"><Badge tone={view.demo ? 'amber' : 'neutral'}>{view.demo ? 'Fictional sample' : view.active ? 'Live search' : 'Saved run'}</Badge><time aria-label="Elapsed search time">{elapsedLabel(run.created, view.active ? now : view.lastAt || run.created)}</time>
        {view.active && <button className="secondary-button stop-button" onClick={stop} disabled={stopping} title="Stop local work. Requests already sent to Nimble may continue."><Square size={12}/>{stopping ? 'Stopping…' : 'Stop'}</button>}
        {(!view.active || !!events.length) && <button className={'secondary-button trace-toggle ' + (traceOpen ? 'selected' : '')} onClick={() => setTraceOpen(value => !value)} aria-expanded={traceOpen} aria-controls="activity-trace"><ListTree size={15}/>{traceOpen ? 'Hide activity' : 'Activity'}<span className="activity-count">{events.length || '—'}</span></button>}</div>
    </div>
    {stopError && <div className="notice error" role="alert">{stopError}</div>}
    {run.status === 'stopped' && <div className="notice" role="status">{events.find(event => event.type === 'run_stopped')?.message || 'Search stopped. Results already received were kept.'}</div>}
    {(connection === 'reconnecting' || error || run.error) && <div className="notice error" role="alert"><CircleAlert size={16}/><div><strong>{connection === 'reconnecting' ? 'The connection was interrupted.' : 'This search needs attention.'}</strong><p>{run.error || error}</p>{connection === 'reconnecting' && <p>The server may still be working. Reconnecting only reads the existing run.</p>}</div><button className="text-button" onClick={reconnect}><RefreshCw size={14}/>Reconnect</button></div>}
    {traceOpen && <TracePanel events={events} run={run} demo={view.demo} transport={transport} connection={connection} traceUrl={repository.traceUrl(run.id)} focus={focus} now={now} onClose={() => setTraceOpen(false)}/>}
    {view.location && <p className="location-default">Searching {view.location.text}{view.location.source === 'resume' ? ' · from your résumé' : ' · your preference'}</p>}
    {view.publicResearch && view.publicResearch.status !== 'skipped' && <details className="public-work-summary"><summary>Public work · {view.publicResearch.status === 'failed' ? 'research unavailable' : `${view.publicResearch.facts.length} source-checked findings`}</summary>{view.publicResearch.facts.map(fact => <p key={fact.id}>{fact.claim} <SourceLink url={fact.source_url}>Source</SourceLink></p>)}<p>Confirm personal attribution before adding any finding to your résumé.</p></details>}
    <div className="results-layout">
      <div className="results-column">{(hasResults || !view.active) && <>
        <div className="results-toolbar"><div className="result-tabs" role="tablist" aria-label="Result types"><button ref={matchesTab} role="tab" id="matches-tab" aria-selected={tab === 'matches'} aria-controls="result-list" tabIndex={tab === 'matches' ? 0 : -1} onKeyDown={keyboardTab} onClick={() => {switched.current = true; setTab('matches');}}>Matches <span>{view.jobs.length}</span></button>
          <button ref={reviewTab} role="tab" id="review-tab" aria-selected={tab === 'review'} aria-controls="result-list" tabIndex={tab === 'review' ? 0 : -1} onKeyDown={keyboardTab} onClick={() => {switched.current = true; setTab('review');}}>Needs review <span>{view.unknowns.length}</span></button>{!!view.candidates.length && <button ref={checkingTab} role="tab" id="checking-tab" aria-selected={tab === 'checking'} aria-controls="result-list" tabIndex={tab === 'checking' ? 0 : -1} onKeyDown={keyboardTab} onClick={() => {switched.current = true; setTab('checking');}}>{view.active ? 'Checking' : 'Unverified'} <span>{view.candidates.length}</span></button>}</div>{run.result && <a className="text-button" href={repository.exportUrl(run.id)}><Download size={14}/>Export</a>}</div>
        {!view.active && !view.jobs.length && !!view.unknowns.length && <div className="review-banner"><CircleAlert size={16}/><p>No confirmed matches. Review the missing evidence below.</p></div>}
        <div id="result-list" className="job-grid" role="tabpanel" aria-labelledby={tab + '-tab'}>
          {jobs.map(job => <JobCard key={job.id} job={job} review={tab === 'review'} demo={view.demo} onTrace={follow} proposal={view.proposals[job.id]} onDraft={edits => repository.resumeDraft(run.id,job.id,edits)} canTailor={!view.active && !!view.publicResearch?.facts.length} onTailor={async () => {await repository.tailor(run.id,job.id);reconnect();}}/>)}
          {tab === 'checking' && view.candidates.map(item => <CandidateCard key={item.id} candidate={item} active={view.active} onTrace={follow}/>)}
          {!jobs.length && !(tab === 'checking' && view.candidates.length) && <div className="empty-results">{view.active ? <LoaderCircle className="spin" size={23}/> : <FileEmpty/>}<h3>{view.active ? 'Checking the evidence' : tab === 'review' ? 'Nothing waiting for review' : 'No confirmed matches'}</h3><p>{view.active ? 'Research can take a few minutes. Follow the actual calls in Activity while the search continues.' : tab === 'review' ? 'No openings were placed in this list.' : run.status === 'stopped' ? 'Stopped before any confirmed matches were received.' : run.result ? view.candidates.length ? 'Some sources could not be verified. This does not establish that you are unsuitable for those roles.' : 'No checked matches were established. See the sources and decisions below.' : 'This search stopped before a shortlist was completed.'}</p>{!view.active && <button className="text-button" onClick={onEdit}>Edit preferences<ArrowRight size={14}/></button>}</div>}
        </div>
        {!!run.result?.shortfall && !!view.jobs.length && <div className="shortfall-note"><p>{view.jobs.length} of {run.count} requested matches.</p><button className="text-button" onClick={onEdit}>Adjust preferences<ArrowRight size={14}/></button></div>}
        </>}{!!view.excluded.length && <details className="excluded-list"><summary>Not included <span>{view.excluded.length}</span></summary>{view.excluded.map((item, index) => <div key={item.url + index}>{view.demo ? <strong>{item.title}</strong> : <SourceLink url={item.url}>{item.title || item.url}</SourceLink>}<p>{item.reason}</p><button className="text-button" onClick={() => follow(item.url)}>View trace<ArrowRight size={12}/></button></div>)}</details>}
        {!!run.result?.warnings?.length && <div className="notice">{run.result.warnings.join(' ')}</div>}
      </div>
    </div>
  </section>;
}
function FileEmpty() {return <ListTree size={23}/>;}
