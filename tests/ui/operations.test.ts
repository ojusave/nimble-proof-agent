import {expect, it} from 'vitest';
import {recordedOperations} from '../../ui/core/operations';

it('keeps successful retrieval separate from failed research and final inclusion', () => {
  const steps = recordedOperations({status: 'error', output: {page: {characters: 300}}, updates: [
    {event: 'tool_started', step: 'extract', at: '2026-11-02T00:00:00Z'},
    {event: 'extraction_ready', step: 'extract', at: '2026-11-02T00:00:02Z'},
    {event: 'tool_started', step: 'match', at: '2026-11-02T00:00:03Z'},
  ]});
  expect(steps.map(step => step.status)).toEqual(['Output received', 'No output recorded']);
  expect(steps[0].ended).toBe('2026-11-02T00:00:02Z');
  expect(steps[1].ended).toBeUndefined();
});
it('does not invent an agent call when extraction stops the candidate', () => {
  const steps = recordedOperations({status: 'done', output: {page: {}}, updates: [{event: 'tool_started', step: 'extract'}]});
  expect(steps.map(step => step.name)).toEqual(['Extract page']);
});
