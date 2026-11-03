'use client';
import {useEffect, useMemo, useRef, useState} from 'react';
import {Check, ChevronDown, Download, LoaderCircle, Search, FileText, ListTree, CircleAlert, X} from 'lucide-react';
import {createActivityState, applyActivityEvent, finishActivity, describeStage} from '../core/activity.mjs';
import type {ActivityEvent, ConnectionStatus, SearchRun} from '../core/types';
import {recordedOperations} from '../core/operations';
import {Badge, SourceLink, sourceHost, elapsedLabel} from './shared';
import {ExecutionTrace} from './ExecutionTrace';

function stageTitle(stage: any) {
  const name = {resume: 'Read résumé', search: 'Find openings', check: 'Investigate & check', profile:'Research public work',tailor:'Connect evidence to roles',shortlist: 'Build shortlist'}[stage.kind as string];
  return (name || stage.kind) + (stage.round > 1 ? ` · round ${stage.round}` : '');
}
function Call({call, focus, demo, now}: {call: any; focus?: {url: string; version: number}; demo: boolean; now: number}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (focus && focus.url === call.input.url) {
      setOpen(true);
      requestAnimationFrame(() => ref.current?.scrollIntoView({block: 'nearest', behavior: 'smooth'}));
    }
  }, [focus, call.input.url]);
  const outcome = call.status === 'error' ? 'Issue' : call.verdict || (call.status === 'active' ? call.phase || 'Starting' : call.status === 'ended' ? 'Ended without a result' : call.status === 'stopped' ? 'Stopped' : 'Done');
  const updates = call.updates as any[];
  const duration = call.startedAt ? elapsedLabel(call.startedAt, call.status === 'active' ? now : call.updatedAt) : '';
  return <details className={'trace-call ' + call.status} ref={ref} open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary><span className="call-title">{call.label.replace(/^Job Application for /i, '')}</span><span className="call-outcome">{outcome}</span><ChevronDown size={13}/></summary>
    <div className="call-content">
      <div className="call-meta"><div>{[...call.tools].map((tool: any) => <Badge key={tool}>{demo && tool.startsWith('Nimble') ? 'Sample · ' : ''}{tool}</Badge>)}</div><time>{duration}</time></div>
      {call.input.query && <div className="trace-fact"><span>Search query</span><p>{call.input.query}</p></div>}
      {call.input.url && <div className="trace-fact"><span>Source</span><SourceLink url={call.input.url}>{sourceHost(call.input.url)}</SourceLink></div>}
      {call.input.url && <ol className="call-operations">{recordedOperations(call).map(operation => <li key={operation.step}>
        <strong>{operation.name}</strong><span>{operation.status}</span>
        {operation.started && operation.ended && <time>{elapsedLabel(operation.started, operation.ended)}</time>}
      </li>)}</ol>}
      {call.output.queries && <div className="trace-fact"><span>Planned locally</span><ul>{call.output.queries.map((query: string) => <li key={query}>{query}</li>)}</ul></div>}
      {call.output.listings && <div className="trace-fact"><span>{call.output.returned} results returned · {call.output.listings.length} new candidates</span><ul>{call.output.listings.map((item: any) => <li key={item.id}><SourceLink url={item.url}>{item.title}</SourceLink></li>)}</ul></div>}
      {call.output.page && <div className="trace-fact"><span>Page retrieved</span><p>{call.output.page.characters?.toLocaleString()} characters{call.output.evidence ? ` · ${call.output.evidence.selected_characters.toLocaleString()} selected for assessment` : ''}</p></div>}
      {call.output.research && <div className="trace-fact"><span>Research returned</span><p>{call.output.research.trust?.sources?.length || 0} sources · {call.output.research.trust?.claims?.length || 0} claims</p><p className="evidence-note">Provider output is checked by the app before inclusion.</p></div>}
      {call.output.assessment && <div className={'trace-decision ' + (call.status === 'error' ? 'issue' : '')}><strong>{call.output.assessment.decision}</strong><p>{call.output.assessment.reason || (call.verdict === 'Matched' ? 'Supporting quotations and explicit requirements passed the local checks.' : 'Some required evidence could not be confirmed.')}</p></div>}
      <details className="recorded-events"><summary>Recorded events <span>{updates.length}</span></summary><ol>{updates.map((update, index) => <li key={index}><time>{update.at ? new Date(update.at).toLocaleTimeString([], {hour12: false}) : '—'}</time><span>{update.message}</span></li>)}</ol></details>
      <details className="raw-data"><summary>Inspect event data</summary><p>Saved inputs and outputs. Full résumé input is omitted.</p><pre>{JSON.stringify({input: call.input, output: call.output, events: updates.map(({signature, ...value}) => value)}, null, 2)}</pre></details>
    </div>
  </details>;
}

export function TracePanel({events, run, demo, transport, connection, traceUrl, focus, now, onClose}: {events: ActivityEvent[]; run: SearchRun; demo: boolean; transport: string; connection: ConnectionStatus; traceUrl: string; focus?: {url: string; version: number}; now: number; onClose(): void}) {
  const scroll = useRef<HTMLDivElement>(null), following = useRef(true);
  const active = run.status === 'running' || run.status === 'stopping';
  const state: any = useMemo(() => {
    const value = createActivityState();
    for (const event of events) applyActivityEvent(value, event);
    if (!['running', 'stopping'].includes(run.status)) finishActivity(value, run.status, run.result);
    return value;
  }, [events, run.status, run.result]);
  useEffect(() => {
    if (active && following.current && scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [events.length, active]);
  const metrics = [{icon: Search, label: 'Searches', value: events.filter(e => e.type === 'search_results').length},
    {icon: FileText, label: 'Pages read', value: events.filter(e => e.type === 'extraction_ready').length},
    {icon: Check, label: 'Assessed', value: events.filter(e => e.type === 'research_completed').length}].filter(metric => metric.value > 0);
  if (!events.length && active) return null;
  return <aside className="trace-panel" id="activity-trace" aria-label="Search activity trace">
    <header className="trace-header"><div><ListTree size={18}/><h2>Activity</h2><span className="trace-event-count">{events.length}</span></div><div>
      <a className="icon-button" href={traceUrl} aria-label="Download recorded trace" title="Download trace"><Download size={16}/></a><button className="icon-button" onClick={onClose} aria-label="Close activity"><X size={16}/></button>
    </div></header>
    <div className="trace-intro"><span className={'status-dot ' + (active ? 'pulse' : '')}/>{demo ? 'Fictional sample · no API calls' : active ? 'Updates appear as they arrive' : 'Saved events · original timestamps'}</div>
    {!!metrics.length && <div className="trace-metrics">{metrics.map(({icon: Icon, label, value}) => <div key={label}><Icon size={14}/><strong>{value}</strong><span>{label}</span></div>)}</div>}
    <div className="trace-scroll" ref={scroll} onScroll={event => {const node = event.currentTarget; following.current = node.scrollHeight - node.clientHeight - node.scrollTop < 40;}}>
      {events.filter(event => event.type==='saved_ingestion').map(event => <ExecutionTrace key={event.id} events={event.data.events} active={false} saved/>)}
      <ExecutionTrace events={events} active={active}/>
      {!state.stages.length && <div className="trace-empty">{connection === 'closed' ? <><CircleAlert size={18}/><p>No activity was recorded for this search.</p></> : <><LoaderCircle className="spin" size={18}/><p>{connection === 'connected' ? 'Waiting for the first recorded step…' : 'Connecting to the saved activity…'}</p></>}</div>}
      <ol className="trace-stages">{state.stages.map((stage: any) => <TraceStage key={stage.key} stage={stage} focus={focus} demo={demo} now={now}/>)}</ol>
    </div>
    <footer className="trace-footer">{transport}<span>LangGraph workflow</span></footer>
  </aside>;
}

function TraceStage({stage, focus, demo, now}: {stage: any; focus?: {url: string; version: number}; demo: boolean; now: number}) {
  const [expanded, setExpanded] = useState<boolean | null>(null);
  const open = expanded ?? stage.status === 'active';
  const calls = [...stage.calls.values()] as any[];
  const issues = calls.some(call => call.status === 'error') || stage.status === 'stopped';
  useEffect(() => {if (focus && calls.some(call => call.input.url === focus.url)) setExpanded(true);}, [focus]);
  const Icon = issues ? CircleAlert : stage.status === 'active' ? LoaderCircle : Check;
  return <li className={'trace-stage ' + stage.status + (issues ? ' issue' : '')}>
    <span className="stage-marker"><Icon size={13} className={stage.status === 'active' ? 'spin' : ''}/></span>
    <details open={open} onToggle={event => {if (event.currentTarget.open !== open) setExpanded(event.currentTarget.open);}}><summary><span><strong>{stageTitle(stage)}</strong><small>{describeStage(stage)}</small></span><ChevronDown size={14}/></summary>
      <div className="stage-calls">{calls.map(call => <Call key={call.key} call={call} focus={focus} demo={demo} now={now}/>)}</div>
      {stage.kind === 'shortlist' && stage.result && <p className="trace-final">{stage.result.jobs.length} matches · {stage.result.unknowns?.length || 0} need review. Requirements were not relaxed.</p>}
    </details>
  </li>;
}
