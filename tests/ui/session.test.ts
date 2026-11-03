import {describe, it, expect} from 'vitest';
import {mergeEvent, runView, claimLabel} from '../../ui/core/session';
import type {ActivityEvent, SearchRun} from '../../ui/core/types';

const event = (seq: number, type = 'provider_status', data = {}): ActivityEvent => ({seq, id: String(seq), at: '2026-11-02T10:00:00Z', type, step: 'match', message: type, data});
const run: SearchRun = {id: 'r', query: '', count: 1, status: 'running', result: null, error: null, created: '2026-11-02T10:00:00Z', resume_id: 'resume'};
describe('transport-independent search state', () => {
  it('deduplicates replayed events and orders delayed delivery by stored sequence', () => {
    const first = [event(2), event(4)];
    expect(mergeEvent(first, event(2))).toBe(first);
    expect(mergeEvent(first, event(3)).map(item => item.seq)).toEqual([2, 3, 4]);
  });
  it('uses backend status rather than observer completion to declare a search finished', () => {
    expect(runView(run, []).active).toBe(true);
    expect(runView({...run, status: 'interrupted'}, []).active).toBe(false);
  });
  it('keeps review separate, deduplicates jobs, and caps provisional matches', () => {
    const events = [event(1, 'job_matched', {job: {id: 'a'}}), event(2, 'job_matched', {job: {id: 'a'}}), event(3, 'job_matched', {job: {id: 'b'}}), event(4, 'job_unknown', {job: {id: 'c'}})];
    const view = runView(run, events);
    expect(view.jobs.map(job => job.id)).toEqual(['a']);
    expect(view.unknowns.map(job => job.id)).toEqual(['c']);
  });
  it('labels fictional runs from recorded mode instead of treating fixtures as live calls', () => {
    expect(runView(run, [event(1, 'run_started', {demo: true})]).demo).toBe(true);
  });
  it('turns technical claim paths into meaningful labels without losing requirement identity', () => {
    expect(claimLabel('$.checks.R2.evidence', [{id: 'R2', requirement: 'Remote US'}])).toBe('Requirement: Remote US');
    expect(claimLabel('$.strengths[1].job_quote')).toBe('Fit evidence 2 · listing quote');
    expect(claimLabel('$.open_status')).toBe('Listing availability');
  });
});

it('shows a discovered candidate before research and removes it when its assessment arrives', () => {
  const candidate={id:'a',url:'https://employer.example/jobs/1',title:'Engineer'};
  const discovered=event(1,'candidate_discovered',{candidate});
  expect(runView(run,[discovered]).candidates[0].status).toBe('queued');
  const reading={...event(2,'tool_started',{candidate_id:'a'}),step:'extract'};
  expect(runView(run,[discovered,reading]).candidates[0].status).toBe('reading');
  expect(runView(run,[discovered,reading,event(3,'job_unknown',{job:{id:'a'}})]).candidates).toHaveLength(0);
});
it.each(['provider_error','unverified'])('keeps %s separate from a rejected role', category => {
  const e=event(1,'job_excluded',{candidate_id:'a',url:'https://employer.example/1',title:'Engineer',category,reason:'Evidence unavailable'});
  const view=runView({...run,status:'complete'},[e]);
  expect(view.excluded).toHaveLength(0);expect(view.candidates[0].status).toBe('unverified');
});
it('streams résumé proposals separately from job acceptance', () => {
  const proposal={edits:[{wording:'A proposed addition'}]};
  const view=runView(run,[event(1,'resume_proposals_ready',{candidate_id:'a',proposal})]);
  expect(view.jobs).toHaveLength(0);expect(view.proposals.a).toEqual(proposal);
});
