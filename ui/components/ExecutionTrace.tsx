import {Check, CircleAlert, GitBranch, LoaderCircle} from 'lucide-react';
import type {ActivityEvent} from '../core/types';

export function ExecutionTrace({events,active,saved=false}: {events: ActivityEvent[]; active: boolean; saved?: boolean}) {
  const spans=new Map<string,{start: ActivityEvent; end?: ActivityEvent}>();
  for(const item of events) {
    if(item.type==='node_started') spans.set(item.data.span_id,{start:item});
    if(['node_completed','node_failed'].includes(item.type)) {const span=spans.get(item.data.span_id);if(span) span.end=item;}
  }
  if(!spans.size) return null;
  const parser=events.filter(item => item.type.startsWith('parser_')).at(-1);
  return <div className="execution-trace"><div className="execution-title"><GitBranch size={15}/><strong>{saved ? 'Earlier résumé ingestion' : 'LangGraph execution'}</strong><span>{saved ? 'Reused · not run again' : 'Actual node calls'}</span></div>
    {parser && <p className="parser-status">LlamaIndex LlamaParse · {parser.data.status || 'submitted'} · {parser.data.job_id}</p>}
    {[...spans.values()].map(({start,end}) => {
      const running=!end && active, failed=end?.type==='node_failed';
      const status=running ? 'Running' : failed ? 'Failed' : end ? 'Completed' : 'Interrupted';
      return <details key={start.data.span_id} className={'execution-node '+(start.data.parent_id ? 'child' : '')}>
        <summary>{running ? <LoaderCircle className="spin" size={13}/> : failed || !end ? <CircleAlert size={13}/> : <Check size={13}/>}<code>{start.data.node}</code><span>{start.data.graph}</span><b>{status}</b><time>{end ? `${(end.data.duration_ms/1000).toFixed(2)}s` : ''}</time></summary>
        <div><p>Started {new Date(start.at).toLocaleTimeString()} · span {start.data.span_id}</p>{start.data.parent_id && <p>Parent span {start.data.parent_id}</p>}<h5>Input summary</h5><pre>{JSON.stringify(start.data.input,null,2)}</pre>{end && <><h5>{failed ? 'Error' : 'Returned output summary'}</h5><pre>{JSON.stringify(end.data.output || end.data.error,null,2)}</pre></>}</div>
      </details>;
    })}
  </div>;
}
