// Presentation of real workflow events. No timers advance the workflow or invent progress.
export function createActivityState() {
  return {round: 1, stages: [], candidates: new Map(), seen: new Set(), terminal: null};
}
function stageFor(state, kind, round) {
  const key = kind + ':' + round;
  let stage = state.stages.find(item => item.key === key);
  if (!stage) {
    for (const previous of state.stages) if (previous.status === 'active') previous.status = 'done';
    stage = {key, kind, round, status: 'active', calls: new Map(), found: new Set(), read: new Set(), outcomes: new Map()};
    state.stages.push(stage);
  }
  return stage;
}
function callFor(stage, key, label, tool) {
  if (!stage.calls.has(key)) stage.calls.set(key, {key, label, tools: new Set(), status: 'active', phase: '', input: {}, output: {}, updates: []});
  const call = stage.calls.get(key);
  if (tool) call.tools.add(tool.replace(' API', ''));
  return call;
}
function remember(call, event) {
  const data = {...event.data};
  delete data.job; delete data.result; delete data.tool;
  const update = {event: event.type, message: event.message, ...data};
  // Heartbeats replace the previous identical status instead of becoming new log rows.
  const signature = JSON.stringify(update);
  if (!call.updates.some(item => JSON.stringify(item) === signature)) call.updates.push(update);
}
export function applyActivityEvent(state, event) {
  const identity = event.seq ?? event.id;
  if (identity !== undefined && state.seen.has(identity)) return;
  if (identity !== undefined) state.seen.add(identity);
  if (state.terminal) return;
  const data = event.data || {}, type = event.type;
  if (type === 'run_started') return;
  if (event.step === 'plan' && data.round) state.round = Math.max(state.round, data.round);
  const round = data.round || state.round;
  if (type === 'search_completed') {
    const stage = stageFor(state, 'shortlist', round);
    stage.result = data.result;
    stage.status = 'done'; state.terminal = 'complete';
    return;
  }
  if (type === 'run_failed') {
    state.terminal = 'failed';
    const stage = state.stages.at(-1) || stageFor(state, 'shortlist', round);
    stage.status = 'stopped'; stage.error = event.message;
    for (const call of stage.calls.values()) if (call.status === 'active') call.status = 'stopped';
    return;
  }
  if (event.step === 'resume') {
    const stage = stageFor(state, 'resume', 0);
    const call = callFor(stage, 'resume', 'Read résumé', 'Local parser');
    if (type === 'step_completed') { call.status = 'done'; call.output = {characters: data.characters}; stage.status = 'done'; }
    remember(call, event); return;
  }
  if (event.step === 'plan' || event.step === 'search' && type !== 'round_completed') {
    const stage = stageFor(state, 'search', round);
    const planning = event.step === 'plan';
    const key = planning ? 'plan' : data.query || stage.lastQuery || 'search';
    if (data.query) stage.lastQuery = data.query;
    const call = callFor(stage, key, planning ? 'Plan search' : data.query || key, planning ? 'Nimble Agent' : 'Nimble Search');
    if (data.query) call.input = {query: data.query};
    if (type === 'provider_status') call.phase = data.status;
    if (type === 'provider_progress') call.phase = event.message;
    if (type === 'plan_ready') {
      call.status = 'done'; call.phase = '';
      call.output = {queries: data.queries, requirements: data.requirements};
    }
    if (type === 'search_results') {
      call.status = 'done'; call.phase = '';
      call.output = {listings: data.candidates || [], returned: data.total_returned};
      for (const candidate of data.candidates || []) {
        state.candidates.set(candidate.id, candidate);
        stage.found.add(candidate.url);
      }
    }
    if (type === 'tool_failed') { call.status = 'error'; call.phase = event.message; }
    remember(call, event); return;
  }
  if (type === 'round_completed') {
    const stage = stageFor(state, 'check', round);
    stage.status = 'done'; stage.totals = data;
    return;
  }
  if (!['extract', 'match', 'verify'].includes(event.step)) return;
  const stage = stageFor(state, 'check', round);
  const candidateId = data.candidate_id || data.candidate_ids?.[0] || data.job?.id;
  const candidate = state.candidates.get(candidateId);
  const url = data.url || data.job?.url || candidate?.url;
  // Older saved runs didn't attach candidate IDs to hosted-provider status events.
  // Keep those updates at stage level rather than assigning them to the wrong listing.
  if (!url && !candidateId) {
    if (type.startsWith('provider_')) stage.providerStatus = data.status || event.message;
    return;
  }
  const key = url || candidateId;
  const call = callFor(stage, key, data.job?.title || data.title || candidate?.title || url || 'Job listing', data.tool);
  if (url) call.input = {url};
  if (type === 'tool_started') {
    call.phase = event.step === 'extract' ? 'Reading page' : 'Checking fit';
    call.tools.add(event.step === 'extract' ? 'Nimble Extract' : 'Nimble Agent');
  }
  if (type === 'extraction_ready') {
    stage.read.add(key);
    call.output.page = {characters: data.characters, preview: data.preview};
    call.phase = 'Page read';
  }
  if (type === 'provider_status') call.phase = data.status === 'completed' ? 'Validating evidence' : 'Checking fit · ' + data.status;
  if (type === 'provider_progress') call.phase = event.message;
  if (['job_matched', 'job_unknown', 'job_excluded'].includes(type)) {
    call.status = 'done';
    call.verdict = type === 'job_matched' ? 'Matched' : type === 'job_unknown' ? 'Needs review' : 'Excluded';
    call.phase = '';
    call.output.assessment = data.job ? {decision: call.verdict, title: data.job.title, company: data.job.company, fit: data.job.fit, requirements: data.job.checks} : {decision: call.verdict, reason: data.reason};
    if (type === 'job_excluded' && /failed|HTTP \d|unavailable|could not be read|connection|readable content/i.test(data.reason || '')) {
      call.status = 'error'; call.phase = data.reason;
    }
    stage.outcomes.set(key, call.verdict);
  }
  remember(call, event);
}
export function finishActivity(state, status, result) {
  if (status === 'complete' && !state.terminal) {
    const stage = stageFor(state, 'shortlist', state.round);
    stage.result = result; stage.status = 'done';
  }
  state.terminal = status;
  for (const stage of state.stages) {
    if (stage.status === 'active') stage.status = status === 'complete' ? 'done' : 'stopped';
    for (const call of stage.calls.values()) if (call.status === 'active') call.status = status === 'complete' ? 'ended' : 'stopped';
  }
}
export function describeStage(stage) {
  const errors = [...stage.calls.values()].filter(call => call.status === 'error').length;
  const issue = errors ? ' · ' + errors + (errors === 1 ? ' issue' : ' issues') : '';
  if (stage.error) return stage.error;
  if (stage.kind === 'resume') return stage.status === 'active' ? 'Reading your experience' : 'Ready for matching';
  if (stage.kind === 'search') {
    const searches = [...stage.calls.values()].filter(call => call.key !== 'plan');
    if (!searches.length) {
      const plan = stage.calls.get('plan');
      return plan?.status === 'done' ? (plan.output.queries?.length || 0) + ' queries ready' : plan?.phase === 'queued' ? 'Planning · queued' : 'Planning targeted queries';
    }
    return searches.length + (searches.length === 1 ? ' search' : ' searches') + ' · ' + stage.found.size + ' listings found' + issue;
  }
  if (stage.kind === 'check') {
    if (stage.status === 'active') return stage.read.size + ' read · ' + stage.outcomes.size + ' checked' + issue;
    const counts = {Matched: 0, 'Needs review': 0, Excluded: 0};
    for (const verdict of stage.outcomes.values()) counts[verdict]++;
    return stage.outcomes.size ? [counts.Matched + ' matched', counts['Needs review'] ? counts['Needs review'] + ' need review' : '', counts.Excluded ? counts.Excluded + ' excluded' : ''].filter(Boolean).join(' · ') + issue : 'No new listings to check';
  }
  return stage.result ? stage.result.jobs.length + ' of ' + stage.result.requested + ' matches ready' : 'Ordering checked matches';
}
function titleFor(stage) {
  return stage.kind === 'resume' ? 'Read résumé' : stage.kind === 'search' ? stage.round > 1 ? 'Search again · round ' + stage.round : 'Search employer sites' : stage.kind === 'check' ? stage.round > 1 ? 'Check listings · round ' + stage.round : 'Check listings' : 'Rank shortlist';
}
function node(tag, text, className) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  if (className) result.className = className;
  return result;
}
function updateText(element, text) { if (element.textContent !== text) element.textContent = text; }
export class ActivityTimeline {
  constructor(host, headline) {
    this.host = host; this.headline = headline;
    this.reset();
  }
  reset(replay = false) {
    this.state = createActivityState(); this.rows = new Map();
    this.host.replaceChildren(); this.host.dataset.replay = String(replay);
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = null;
  }
  add(event) { applyActivityEvent(this.state, event); this.schedule(); }
  finish(status, result) { finishActivity(this.state, status, result); this.schedule(); }
  schedule() {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => { this.frame = null; this.render(); });
  }
  render() {
    const entering = [];
    for (const stage of this.state.stages) {
      if (!this.rows.has(stage.key)) {
        const item = node('li', undefined, 'timeline-step');
        const marker = node('span', undefined, 'step-marker'); marker.setAttribute('aria-hidden', 'true');
        const detail = node('details', undefined, 'stage-detail');
        const summary = node('summary', undefined, 'step-summary');
        const heading = node('span', undefined, 'step-heading');
        const title = node('strong', titleFor(stage), 'step-title');
        const outcome = node('span', undefined, 'step-outcome');
        heading.append(title, outcome);
        const status = node('span', undefined, 'step-status');
        summary.append(heading, status);
        const calls = node('div', undefined, 'stage-calls');
        detail.append(summary, calls); item.append(marker, detail); this.host.append(item); entering.push(item);
        this.rows.set(stage.key, {item, outcome, status, calls, records: new Map()});
      }
      const row = this.rows.get(stage.key);
      const hasIssues = [...stage.calls.values()].some(call => call.status === 'error');
      row.item.className = 'timeline-step ' + stage.status + (hasIssues ? ' has-issues' : '');
      updateText(row.outcome, describeStage(stage));
      updateText(row.status, stage.status === 'active' ? 'In progress' : stage.status === 'stopped' ? 'Stopped' : hasIssues ? 'Issues' : 'Done');
      for (const call of stage.calls.values()) {
        if (!row.records.has(call.key)) {
          const detail = node('details', undefined, 'tool-call');
          const summary = node('summary');
          const name = node('span', undefined, 'call-name'), status = node('span', undefined, 'call-status');
          summary.append(name, status);
          const body = node('div', undefined, 'call-body');
          const tool = node('p', undefined, 'call-tool');
          const inputs = node('pre'), outputs = node('pre');
          const raw = node('details', undefined, 'raw-events'); raw.append(node('summary', 'Provider updates'));
          const rawText = node('pre'); raw.append(rawText);
          body.append(tool, node('h5', 'Input'), inputs, node('h5', 'Output'), outputs, raw);
          detail.append(summary, body); row.calls.append(detail);
          row.records.set(call.key, {detail, name, status, tool, inputs, outputs, rawText});
        }
        const record = row.records.get(call.key);
        record.detail.dataset.status = call.status;
        updateText(record.name, call.label.replace(/^Job Application for /i, ''));
        updateText(record.status, call.status === 'error' ? 'Issue' : call.verdict || (call.status === 'ended' ? 'Ended' : call.status === 'stopped' ? 'Stopped' : call.status === 'done' ? 'Done' : call.phase || 'Running'));
        updateText(record.tool, [...call.tools].join(' → '));
        updateText(record.inputs, Object.keys(call.input).length ? JSON.stringify(call.input, null, 2) : 'Local résumé text is kept out of this log.');
        updateText(record.outputs, Object.keys(call.output).length ? JSON.stringify(call.output, null, 2) : call.phase || 'Waiting for output');
        updateText(record.rawText, JSON.stringify(call.updates, null, 2));
      }
    }
    const motion = this.host.dataset.replay !== 'true' && !matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (motion) for (const item of entering) {
      const height = item.getBoundingClientRect().height;
      const padding = getComputedStyle(item).paddingBottom;
      item.animate([{height: '0px', paddingBottom: '0px', opacity: 0}, {height: height + 'px', paddingBottom: padding, opacity: 1}], {duration: 260, easing: 'cubic-bezier(.2,.7,.2,1)'});
    }
    const active = this.state.stages.find(stage => stage.status === 'active');
    const text = this.state.terminal === 'complete' ? 'Search complete' : this.state.terminal ? 'Search stopped' : active ? titleFor(active) : 'Starting search';
    if (this.headline.textContent !== text) {
      updateText(this.headline, text);
      if (motion) {
        this.headline.animate([{opacity: .35, transform: 'translateY(3px)'}, {opacity: 1, transform: 'translateY(0)'}], {duration: 180, easing: 'ease-out'});
      }
    }
  }
}
