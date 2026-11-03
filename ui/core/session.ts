import type {ActivityEvent, SearchRun} from './types';

export function mergeEvent(events: ActivityEvent[], event: ActivityEvent): ActivityEvent[] {
  if (!event || typeof event.seq !== 'number' || typeof event.type !== 'string') return events;
  if (events.some(item => item.seq === event.seq)) return events;
  return [...events, event].sort((a, b) => a.seq - b.seq);
}

export function runView(run: SearchRun, events: ActivityEvent[]) {
  const matched = new Map(), review = new Map();
  const excluded = [];
  let demo = run.result?.mode === 'synthetic demo';
  for (const event of events) {
    if (event.type === 'run_started') demo = !!event.data.demo;
    if (event.type === 'job_matched') matched.set(event.data.job.id, event.data.job);
    if (event.type === 'job_unknown') review.set(event.data.job.id, event.data.job);
    if (event.type === 'job_excluded') excluded.push(event.data);
  }
  return {
    jobs: run.result?.jobs ?? [...matched.values()].slice(0, run.count),
    unknowns: run.result?.unknowns ?? [...review.values()],
    excluded: run.result?.excluded ?? excluded, demo,
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
