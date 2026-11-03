// Presentation of real workflow events. No timers advance the workflow or invent progress.
export function createActivityState() {
  return {round: 1, stages: [], candidates: new Map(), seen: new Set(), terminal: null};
}
function stageFor(state, kind, round) {
  const key = kind + ':' + round;
  let stage = state.stages.find(item => item.key === key);
  if (!stage) {
    for (const previous of state.stages) if (previous.status === 'active' && !['profile','tailor'].includes(previous.kind) && !['profile','tailor'].includes(kind)) previous.status = 'done';
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
  if (!call.startedAt && event.at) call.startedAt = event.at;
  if (event.at) call.updatedAt = event.at;
  const data = {...event.data};
  delete data.job; delete data.result; delete data.tool;
  const update = {event: event.type, step: event.step, message: event.message, ...data};
  // Heartbeats replace the previous identical status instead of becoming new log rows.
  const signature = JSON.stringify(update);
  if (!call.updates.some(item => item.signature === signature)) call.updates.push({...update, at: event.at, signature});
}
export function applyActivityEvent(state, event) {
  const identity = event.seq ?? event.id;
  if (identity !== undefined && state.seen.has(identity)) return;
  if (identity !== undefined) state.seen.add(identity);
  if(event.type==='tailoring_requested') state.terminal=null;
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
  if (type === 'run_stopping') return;
  if (type === 'run_failed' || type === 'run_stopped') {
    state.terminal = type === 'run_stopped' ? 'stopped' : 'failed';
    if (!state.stages.length) return;
    const stage = state.stages.at(-1) || stageFor(state, 'shortlist', round);
    stage.status = 'stopped';
    if (type === 'run_failed') stage.error = event.message;
    for (const call of stage.calls.values()) if (call.status === 'active') {
      call.status = 'stopped'; call.output.error = event.message; remember(call, event);
    }
    return;
  }
  if (event.step === 'resume') {
    const stage = stageFor(state, 'resume', 0);
    const call = callFor(stage, 'resume', 'Read résumé', data.tool || 'Stored résumé');
    if (type === 'step_completed') { call.status = 'done'; call.output = {characters: data.characters}; stage.status = 'done'; }
    remember(call, event); return;
  }
  if (['profile','tailor'].includes(event.step)) {
    const stage=stageFor(state,event.step,0);
    const key=data.candidate_id || data.url || 'applicant';
    const call=callFor(stage,key,event.step === 'profile' ? data.url || 'Public professional work' : data.url || 'Role-specific résumé suggestions',data.tool || 'Nimble Agent');
    if(data.url) call.input={url:data.url};
    if(type === 'provider_status') call.phase=data.status;
    if(type === 'provider_progress') call.phase=event.message;
    if(type === 'profile_source_checked') {call.status='done';call.output.page={characters:data.characters};}
    if(type === 'profile_research_completed') {call.status='done';call.output.research=data.public_research.research;stage.status='done';}
    if(type === 'resume_proposals_ready') {call.status='done';call.output.research=data.proposal.research;call.output.proposal=data.proposal;}
    if(type.endsWith('_failed')) {call.status='error';call.phase=event.message;stage.status='done';}
    remember(call,event);return;
  }
  if(type === 'candidate_discovered') {state.candidates.set(data.candidate.id,data.candidate);return;}
  if(type === 'listing_links_found') {
    for(const candidate of data.links || []) state.candidates.set(candidate.id,candidate);
    return;
  }
  if (event.step === 'plan' || event.step === 'search' && type !== 'round_completed') {
    const stage = stageFor(state, 'search', round);
    const planning = event.step === 'plan';
    const key = planning ? 'plan' : data.query || stage.lastQuery || 'search';
    if (data.query) stage.lastQuery = data.query;
    const call = callFor(stage, key, planning ? 'Plan search' : data.query || key, data.tool || (planning ? 'Nimble Agent' : 'Nimble Search'));
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
  if (type === 'evidence_selected') call.output.evidence = data.evidence;
  if (type === 'research_completed') {
    call.output.research = data.research;
    call.phase = 'Validating evidence';
  }
  if (type === 'provider_status') call.phase = data.status === 'completed' ? 'Validating evidence' : 'Checking fit · ' + data.status;
  if (type === 'provider_progress') call.phase = event.message;
  if (['job_matched', 'job_unknown', 'job_excluded'].includes(type)) {
    call.status = 'done';
    call.verdict = type === 'job_matched' ? 'Matched' : type === 'job_unknown' ? 'Needs review' : 'Excluded';
    call.phase = '';
    call.output.assessment = data.job ? {decision: call.verdict, title: data.job.title, company: data.job.company, fit: data.job.fit, requirements: data.job.checks} : {decision: call.verdict, reason: data.reason};
    if (type === 'job_excluded' && (data.category === 'provider_error' || /Matching failed:|Source unavailable|HTTP \d|could not be read|connection failed|Not enough readable content/i.test(data.reason || ''))) {
      call.status = 'error'; call.phase = data.reason; call.verdict='Unverified';call.output.assessment.decision='Unverified';
    }
    stage.outcomes.set(key, call.verdict);
  }
  remember(call, event);
}
export function finishActivity(state, status, result) {
  // A snapshot must never invent a step ahead of its recorded event.
  state.terminal = status;
  for (const stage of state.stages) {
    if (stage.status === 'active') stage.status = status === 'complete' ? 'done' : 'stopped';
    for (const call of stage.calls.values()) if (call.status === 'active') call.status = status === 'complete' ? 'ended' : 'stopped';
  }
}
export function describeStage(stage) {
  const errors = [...stage.calls.values()].filter(call => call.status === 'error').length;
  const issue = errors ? ' · ' + errors + (errors === 1 ? ' issue' : ' issues') : '';
  if (stage.error) return 'Couldn’t finish this step';
  if (stage.status === 'stopped') return 'Stopped before this step finished';
  if (stage.kind === 'resume') return stage.status === 'active' ? 'Reading your experience' : 'Ready for matching';
  if (stage.kind === 'profile') return stage.status === 'active' ? 'Following public professional evidence' : 'Professional evidence for your review'+issue;
  if (stage.kind === 'tailor') return stage.status === 'active' ? 'Connecting evidence to job requirements' : 'Résumé suggestions ready for review'+issue;
  if (stage.kind === 'search') {
    const searches = [...stage.calls.values()].filter(call => call.key !== 'plan');
    if (!searches.length) {
      const plan = stage.calls.get('plan');
      return plan?.status === 'done' ? (plan.output.queries?.length || 0) + ' queries ready' : plan?.phase === 'queued' ? 'Planning · queued' : 'Planning targeted queries';
    }
    const returned = searches.some(call => call.output.listings);
    return searches.length + (searches.length === 1 ? ' search' : ' searches') + (returned ? ' · ' + stage.found.size + ' listings found' : ' in progress') + issue;
  }
  if (stage.kind === 'check') {
    if (stage.status === 'active') return [stage.read.size ? stage.read.size + ' pages read' : '', stage.outcomes.size ? stage.outcomes.size + ' checked' : 'Investigating openings'].filter(Boolean).join(' · ') + issue;
    const counts = {Matched: 0, 'Needs review': 0, Excluded: 0, Unverified:0};
    for (const verdict of stage.outcomes.values()) counts[verdict]++;
    return stage.outcomes.size ? [counts.Matched + ' matched', counts['Needs review'] ? counts['Needs review'] + ' need review' : '', counts.Excluded ? counts.Excluded + ' excluded' : ''].filter(Boolean).join(' · ') + issue : 'No new listings to check';
  }
  return stage.result ? stage.result.jobs.length + ' of ' + stage.result.requested + ' matches ready' : 'Ordering checked matches';
}
