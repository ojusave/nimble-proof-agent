import type {ActivityEvent, SearchRun, Candidate, ResumeProposal} from './types';

export function mergeEvent(events: ActivityEvent[], event: ActivityEvent): ActivityEvent[] {
  if (!event || typeof event.seq !== 'number' || typeof event.type !== 'string') return events;
  if (events.some(item => item.seq === event.seq)) return events;
  return [...events, event].sort((a, b) => a.seq - b.seq);
}

export function runView(run: SearchRun, events: ActivityEvent[]) {
  const matched = new Map(), review = new Map();
  const candidates = new Map<string,Candidate>();
  const proposals: Record<string,ResumeProposal> = {};
  const excluded = [];
  let location = run.result?.search_location, publicResearch = run.result?.public_research;
  let demo = run.result?.mode === 'synthetic demo';
  for (const event of events) {
    const d = event.data;
    if (event.type === 'run_started') demo = !!d.demo;
    if (event.type === 'plan_ready') location = d.search_location;
    if (event.type === 'candidate_discovered') candidates.set(d.candidate.id,{...d.candidate,status:'queued'});
    if (event.type === 'tool_started' && ['extract','match'].includes(event.step)) {
      for (const id of d.candidate_ids || [d.candidate_id]) {
        const item = candidates.get(id); if (item) candidates.set(id,{...item,status:event.step === 'extract' ? 'reading' : 'researching'});
      }
    }
    if (event.type === 'job_matched') {matched.set(d.job.id,d.job); candidates.delete(d.job.id);}
    if (event.type === 'job_unknown') {review.set(d.job.id,d.job); candidates.delete(d.job.id);}
    if (event.type === 'job_excluded') {excluded.push(d); candidates.delete(d.candidate_id);}
    if (event.type === 'profile_research_completed') publicResearch = d.public_research;
    if (event.type === 'profile_research_failed') publicResearch = {status:'failed',facts:[]};
    if (event.type === 'resume_proposals_ready') proposals[d.candidate_id] = d.proposal;
  }
  const allExcluded = run.result?.excluded ?? excluded;
  for (const item of allExcluded.filter(item => ['provider_error','unverified'].includes(item.category || ''))) {
    const id = item.candidate_id || item.url;
    candidates.set(id,{id,url:item.url,title:item.title,status:'unverified',reason:item.reason});
  }
  return {
    jobs: run.result?.jobs ?? [...matched.values()].slice(0,run.count),
    unknowns: run.result?.unknowns ?? [...review.values()],
    excluded: allExcluded.filter(item => !['provider_error','unverified'].includes(item.category || '')), demo,
    candidates: [...candidates.values()], location, publicResearch,
    proposals: {...proposals,...run.result?.resume_proposals},
    lastAt: events.at(-1)?.at,
    active: run.status === 'running' || run.status === 'stopping',
  };
}

export function claimLabel(path: string | undefined, checks: {id: string; requirement: string}[] = []): string {
  if (!path) return 'Research finding';
  const field = path.replace(/^\$\./, '');
  const names: Record<string, string> = {title: 'Job title', company: 'Employer', location: 'Work location',
    employer_url: 'Employer website', relevance: 'Professional relevance', summary: 'Research summary',
    open_status: 'Listing availability', open_evidence: 'Application instructions', is_specific_opening: 'Individual opening'};
  if (names[field]) return names[field];
  const check = field.match(/^checks\.([^.]+)/);
  if (check) return 'Requirement: ' + (checks.find(item => item.id === check[1])?.requirement ?? check[1]);
  const strength = field.match(/^strengths\[(\d+)\]\.(.+)/);
  if (strength) return `Fit evidence ${Number(strength[1]) + 1} · ${strength[2] === 'job_quote' ? 'listing quote' : strength[2] === 'resume_quote' ? 'résumé quote' : 'interpretation'}`;
  const gap = field.match(/^gaps\[(\d+)\]/);
  if (gap) return 'Potential gap ' + (Number(gap[1]) + 1);
  return field.replaceAll('_', ' ');
}
