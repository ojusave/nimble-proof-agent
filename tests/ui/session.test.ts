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
