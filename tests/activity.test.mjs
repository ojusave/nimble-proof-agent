import assert from 'node:assert/strict';
import {createActivityState, applyActivityEvent, finishActivity, describeStage} from '../web/activity.mjs';
let sequence = 0;
function emit(state, type, step, data = {}, message = type) {
  const event = {seq: ++sequence, type, step, data, message};
  applyActivityEvent(state, event);
  return event;
}
function seeded() {
  const state = createActivityState();
  emit(state, 'step_started', 'plan', {round: 1});
  emit(state, 'plan_ready', 'plan', {round: 1, queries: ['python jobs', 'api jobs']});
  emit(state, 'search_results', 'search', {query: 'python jobs', candidates: [{id: 'a', url: 'https://a.example/job', title: 'Job A'}, {id: 'b', url: 'https://b.example/job', title: 'Job B'}]});
  return state;
}
const checks = [
  ['heartbeats update one call without adding rows', () => {
    const state = createActivityState();
    emit(state, 'step_started', 'plan', {round: 1});
    for (let i = 0; i < 20; i++) emit(state, 'provider_status', 'plan', {status: 'running'}, 'Nimble is running');
    assert.equal(state.stages.length, 1);
    assert.equal(state.stages[0].calls.size, 1);
    assert.equal(state.stages[0].calls.get('plan').updates.length, 2);
  }],
  ['interleaved extraction and assessment stay attached to the right listing', () => {
    const state = seeded();
    emit(state, 'tool_started', 'extract', {candidate_id: 'a', url: 'https://a.example/job'});
    emit(state, 'tool_started', 'extract', {candidate_id: 'b', url: 'https://b.example/job'});
    emit(state, 'extraction_ready', 'extract', {candidate_id: 'b', url: 'https://b.example/job', characters: 400});
    emit(state, 'provider_status', 'match', {candidate_ids: ['b'], status: 'running'});
    emit(state, 'provider_status', 'match', {candidate_ids: ['a'], status: 'queued'});
    const stage = state.stages.at(-1);
    assert.equal(stage.calls.size, 2);
    assert.equal(stage.calls.get('https://a.example/job').phase, 'Checking fit · queued');
    assert.equal(stage.calls.get('https://b.example/job').output.page.characters, 400);
    assert.equal(stage.calls.get('https://b.example/job').phase, 'Checking fit · running');
  }],
  ['replayed events never double-count outcomes', () => {
    const state = seeded();
    const event = emit(state, 'job_matched', 'match', {job: {id: 'a', url: 'https://a.example/job', title: 'Job A'}});
    applyActivityEvent(state, event);
    assert.equal(state.stages.at(-1).outcomes.size, 1);
    assert.equal(state.stages.at(-1).calls.size, 1);
  }],
  ['a failed page remains visible when the rest of the round succeeds', () => {
    const state = seeded();
    emit(state, 'job_excluded', 'verify', {url: 'https://a.example/job', reason: 'Source unavailable'});
    emit(state, 'job_matched', 'match', {job: {id: 'b', url: 'https://b.example/job', title: 'Job B'}});
    emit(state, 'round_completed', 'search', {round: 1});
    const stage = state.stages.at(-1);
    assert.equal(stage.calls.get('https://a.example/job').status, 'error');
    assert.match(describeStage(stage), /1 issue/);
    assert.match(describeStage(stage), /1 matched/);
  }],
  ['a second search round creates new stages without rewriting the first', () => {
    const state = seeded();
    emit(state, 'round_completed', 'search', {round: 1});
    emit(state, 'step_started', 'plan', {round: 2});
    assert.deepEqual(state.stages.map(stage => stage.key), ['search:1', 'check:1', 'search:2']);
    assert.equal(state.stages[0].found.size, 2);
    assert.equal(state.stages[2].found.size, 0);
  }],
  ['late first-round status does not move the active round backwards', () => {
    const state = seeded();
    emit(state, 'round_completed', 'search', {round: 1});
    emit(state, 'step_started', 'plan', {round: 2});
    emit(state, 'provider_status', 'plan', {round: 1, status: 'completed'});
    emit(state, 'tool_started', 'extract', {candidate_id: 'a', url: 'https://a.example/job'});
    assert.equal(state.round, 2);
    assert.equal(state.stages.at(-1).key, 'check:2');
  }],
  ['legacy provider updates are not assigned to an arbitrary candidate', () => {
    const state = seeded();
    emit(state, 'tool_started', 'extract', {candidate_id: 'a', url: 'https://a.example/job'});
    emit(state, 'provider_status', 'match', {status: 'running'});
    assert.equal(state.stages.at(-1).calls.size, 1);
    assert.equal(state.stages.at(-1).calls.get('https://a.example/job').phase, 'Reading page');
  }],
  ['interruption stops the active call without presenting it as success', () => {
    const state = seeded();
    emit(state, 'tool_started', 'extract', {candidate_id: 'a', url: 'https://a.example/job'});
    finishActivity(state, 'interrupted');
    assert.equal(state.stages.at(-1).status, 'stopped');
    assert.equal(state.stages.at(-1).calls.get('https://a.example/job').status, 'stopped');
    assert.equal(state.stages.some(stage => stage.kind === 'shortlist'), false);
  }],
  ['late progress cannot restart a completed timeline', () => {
    const state = seeded();
    emit(state, 'search_completed', 'finish', {result: {jobs: [], requested: 5}});
    emit(state, 'provider_status', 'match', {candidate_ids: ['a'], status: 'running'});
    assert.equal(state.terminal, 'complete');
    assert.equal(state.stages.at(-1).kind, 'shortlist');
    assert.equal(state.stages.at(-1).status, 'done');
  }],
];
for (const [name, run] of checks) { run(); console.log('PASS ' + name); }
console.log(checks.length + ' activity checks passed.');
export const passed = checks.length;
