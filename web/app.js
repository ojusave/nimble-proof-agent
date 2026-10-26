const $ = id => document.getElementById(id);
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
let source = null, runId = null, started = 0, timer = null;
let running = false, uploading = false, demoMode = false, requested = 5;
let tab = 'matches', lastEventAt = 0, finalResult = null;
let matches = new Map(), unknowns = new Map(), exclusions = [], seenEvents = new Set();
const expandedJobs = new Set();

function safeLink(label, url) {
  try { if (new URL(url).protocol !== 'https:') return el('span', label); }
  catch { return el('span', label); }
  const link = el('a', label);
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}
async function api(path, options) {
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); }
  catch { throw new Error('Couldn’t read the server response. Try again.'); }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the form and try again.');
  return data;
}
function busy(value) {
  running = value;
  $('search-button').disabled = value || uploading;
  $('demo-button').disabled = value || uploading;
  $('new-search').disabled = value;
  $('remove-resume').disabled = value;
  $('search-button').replaceChildren(document.createTextNode(value ? 'Searching…' : 'Search jobs'), el('span', value ? '' : '↗'));
  $('search-button').lastChild.setAttribute('aria-hidden', 'true');
  for (const button of $('history').querySelectorAll('button')) button.disabled = value;
}
function elapsed(until = Date.now()) {
  const seconds = Math.max(0, Math.floor((until - started) / 1000));
  $('elapsed').textContent = Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
}
function progress() {
  $('progress-count').textContent = Math.min(matches.size, requested) + ' of ' + requested + ' matches';
}
async function loadResumes(selectId) {
  const rows = await api('/api/resumes');
  const select = $('resume-select'), previous = selectId || select.value;
  select.replaceChildren(...rows.map(resume => {
    const option = el('option', resume.name);
    option.value = resume.id;
    return option;
  }));
  if (rows.some(resume => resume.id === previous)) select.value = previous;
  $('saved-resume').hidden = !rows.length;
  $('upload-title').textContent = rows.length ? 'Replace' : 'Attach résumé';
  return rows;
}
$('resume-file').onchange = async () => {
  const file = $('resume-file').files[0];
  if (!file) return;
  if (file.size > 3 * 1024 * 1024) {
    $('resume-status').textContent = 'Choose a file under 3 MB.';
    return;
  }
  uploading = true;
  busy(running);
  $('resume-status').textContent = 'Reading résumé…';
  try {
    const form = new FormData();
    form.append('file', file);
    const resume = await api('/api/resumes', {method: 'POST', body: form});
    await loadResumes(resume.id);
    $('resume-status').textContent = 'Résumé ready';
  } catch (error) { $('resume-status').textContent = error.message; }
  finally { uploading = false; busy(running); $('resume-file').value = ''; }
};
$('remove-resume').onclick = async () => {
  const id = $('resume-select').value;
  if (!id) return;
  try {
    await api('/api/resumes/' + id, {method: 'DELETE'});
    await loadResumes();
    $('resume-status').textContent = 'Résumé removed. Past results remain.';
  } catch (error) { $('resume-status').textContent = error.message; }
};

function evidenceGroup(title) {
  const section = el('section', undefined, 'evidence-group');
  section.append(el('h4', title));
  return section;
}
function jobCard(job, review) {
  const card = el('article', undefined, 'job-card');
  const main = el('div', undefined, 'job-main');
  const tone = [...job.company].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 4;
  const mark = el('div', job.company.charAt(0).toUpperCase(), 'company-mark tone-' + tone);
  mark.setAttribute('aria-hidden', 'true');
  const text = el('div', undefined, 'job-text');
  text.append(el('h3', job.title));
  const meta = el('div', undefined, 'job-meta');
  meta.append(el('span', job.company, 'company'), el('span', '·', 'separator'), el('span', job.location || 'Location not stated'));
  text.append(meta);
  const fit = job.strengths?.[0]?.reason || job.summary;
  if (fit) text.append(el('p', fit, 'job-fit'));
  if (review) {
    // Collapse repeated planner/query phrasing here; every check stays available in Details.
    const normalize = value => value.toLowerCase().replace(/united states/g, 'us').trim();
    const all = [...new Map((job.unknown_requirements || ['Listing availability']).map(value => [normalize(value), value])).values()];
    const unique = all.filter(value => !all.some(other => normalize(other) !== normalize(value) && normalize(other).includes(normalize(value))));
    text.append(el('p', 'Not confirmed: ' + unique.join(' · '), 'review-note'));
  }
  main.append(mark, text);
  if (job.rank && !review) main.append(el('span', String(job.rank).padStart(2, '0'), 'rank'));
  card.append(main);

  const actions = el('div', undefined, 'job-actions');
  const details = el('details');
  details.open = expandedJobs.has(job.id);
  details.addEventListener('toggle', () => details.open ? expandedJobs.add(job.id) : expandedJobs.delete(job.id));
  details.append(el('summary', 'Details'));
  const content = el('div', undefined, 'evidence-content');
  const fitGroup = evidenceGroup('Why it fits');
  for (const strength of job.strengths || []) {
    fitGroup.append(el('p', strength.reason));
    const pair = el('div', undefined, 'evidence-pair');
    for (const [label, quote] of [['Your résumé', strength.resume_quote], ['Job listing', strength.job_quote]]) {
      const column = el('div');
      column.append(el('span', label, 'evidence-label'), el('blockquote', quote, 'quote'));
      pair.append(column);
    }
    fitGroup.append(pair);
  }
  content.append(fitGroup);
  if (job.gaps?.length) {
    const gaps = evidenceGroup('Gaps');
    for (const gap of job.gaps) gaps.append(el('p', gap, 'gap'));
    content.append(gaps);
  }
  if (job.checks?.length) {
    const requirements = evidenceGroup('Your requirements');
    const labels = {met: 'Confirmed', conflict: 'Conflict', unknown: 'Not confirmed'};
    for (const check of job.checks) {
      const row = el('div', undefined, 'check ' + check.status);
      row.append(el('span', labels[check.status] || 'Not confirmed', 'check-status'), el('strong', check.requirement));
      if (check.evidence) row.append(el('blockquote', check.evidence, 'quote'));
      requirements.append(row);
    }
    content.append(requirements);
  }
  const listing = evidenceGroup('Listing check');
  listing.append(el('p', 'Professional fit: ' + (job.fit === 'strong' ? 'strong' : 'possible')));
  if (job.open_evidence) listing.append(el('blockquote', job.open_evidence, 'quote'));
  else listing.append(el('p', 'Application availability not confirmed.'));
  if (job.checked_at) listing.append(el('p', 'Checked ' + new Date(job.checked_at).toLocaleString()));
  if (demoMode && job.sample_listing) {
    listing.append(el('span', 'Fictional employer listing', 'evidence-label'), el('blockquote', job.sample_listing, 'quote'));
  }
  content.append(listing);
  details.append(content);
  actions.append(details);
  let link;
  if (demoMode) {
    link = el('button', 'Sample listing', 'listing-link');
    link.type = 'button';
    link.onclick = () => {
      details.open = true;
      requestAnimationFrame(() => listing.scrollIntoView({block: 'nearest', behavior: 'smooth'}));
    };
  } else link = safeLink('View opening ↗', job.url);
  actions.append(link);
  card.append(actions);
  return card;
}
function renderJobs() {
  const review = tab === 'review';
  const jobs = review ? [...unknowns.values()] : [...matches.values()].slice(0, requested);
  $('match-count').textContent = Math.min(matches.size, requested);
  $('review-count').textContent = unknowns.size;
  for (const id of ['matches-tab', 'review-tab']) {
    const selected = (id === 'review-tab') === review;
    $(id).setAttribute('aria-selected', String(selected));
    $(id).tabIndex = selected ? 0 : -1;
  }
  $('job-list').setAttribute('aria-labelledby', review ? 'review-tab' : 'matches-tab');
  $('job-list').replaceChildren(...jobs.map(job => jobCard(job, review)));
  if (!jobs.length) $('job-list').append(el('div', review ? 'No openings need review.' : running ? 'Checked matches will appear here.' : 'No openings met all requirements.', 'waiting-card'));
  progress();
}
function selectTab(value, focus = false) {
  tab = value;
  renderJobs();
  if (focus) $(value === 'review' ? 'review-tab' : 'matches-tab').focus();
}
$('matches-tab').onclick = () => selectTab('matches');
$('review-tab').onclick = () => selectTab('review');
for (const id of ['matches-tab', 'review-tab']) $(id).onkeydown = event => {
  if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
    event.preventDefault();
    selectTab(event.key === 'Home' ? 'matches' : event.key === 'End' ? 'review' : tab === 'matches' ? 'review' : 'matches', true);
  }
};
function stageFor(event) {
  if (event.type === 'search_completed') return 'Search complete';
  if (event.type === 'run_failed') return 'Search stopped';
  const stages = {start: 'Starting search', resume: 'Reading résumé', plan: 'Planning search', search: 'Searching employer sites', extract: 'Reading job listings', match: 'Checking fit', verify: 'Checking requirements', finish: 'Finishing search'};
  const stage = stages[event.step] || event.message;
  return event.type === 'provider_status' && ['queued', 'running'].includes(event.data?.status) ? stage + ' · ' + event.data.status : stage;
}
function addEvent(event) {
  if (seenEvents.has(event.seq)) return;
  seenEvents.add(event.seq);
  lastEventAt = Math.max(lastEventAt, new Date(event.at).getTime());
  const data = event.data || {};
  const tool = data.tool || (event.step === 'resume' ? 'Local parser' : 'Workflow');
  const item = el('li');
  item.append(el('div', demoMode && tool.startsWith('Nimble') ? 'Sample · ' + tool : tool, 'tool-label'), el('div', event.message, 'event-message'));
  const info = {...data};
  delete info.job;
  delete info.result;
  if (Object.keys(info).length) {
    const details = el('details', undefined, 'event-details');
    details.append(el('summary', event.type === 'search_results' ? 'Listings' : event.type === 'plan_ready' ? 'Search plan' : 'Input / output'), el('pre', JSON.stringify(info, null, 2)));
    item.append(details);
  }
  item.append(el('div', new Date(event.at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'}), 'event-time'));
  const feed = $('activity-feed');
  const atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 50;
  feed.append(item);
  if (atBottom) feed.scrollTop = feed.scrollHeight;
  $('stage').textContent = stageFor(event);
  if (event.type === 'job_matched') { matches.set(data.job.id, data.job); renderJobs(); }
  if (event.type === 'job_unknown') { unknowns.set(data.job.id, data.job); renderJobs(); }
  if (event.type === 'job_excluded') { exclusions.push(data); renderExcluded(); }
  if (event.type === 'search_completed') complete(data.result);
  if (event.type === 'run_failed') $('message').textContent = event.message;
}
function renderExcluded() {
  $('excluded-section').hidden = !exclusions.length;
  $('excluded-title').textContent = 'Excluded (' + exclusions.length + ')';
  $('excluded-list').replaceChildren(...exclusions.map(job => {
    const row = el('div');
    row.append(demoMode ? el('strong', job.title || 'Sample listing') : safeLink(job.title || job.url, job.url), el('p', job.reason));
    return row;
  }));
}
function editPreferences() {
  $('query').focus();
  $('search-form').scrollIntoView({behavior: 'smooth', block: 'center'});
}
function complete(result) {
  finalResult = result;
  demoMode = result.mode === 'synthetic demo';
  $('demo-note').hidden = !demoMode;
  $('stage').textContent = 'Search complete';
  matches = new Map(result.jobs.map(job => [job.id, job]));
  unknowns = new Map(result.unknowns.map(job => [job.id, job]));
  exclusions = result.excluded;
  renderJobs();
  renderExcluded();
  $('result-title').textContent = 'Your shortlist';
  $('shortfall').hidden = !result.shortfall;
  if (result.shortfall) {
    const box = $('shortfall');
    const reviewCount = result.unknowns.length;
    const explanation = reviewCount ? ' ' + reviewCount + (reviewCount === 1 ? ' opening needs' : ' openings need') + ' confirmation.' : '';
    box.replaceChildren(el('p', result.jobs.length + ' of ' + result.requested + ' matches found.' + explanation));
    if (reviewCount) {
      const review = el('button', 'Review openings', 'text-button');
      review.type = 'button';
      review.onclick = () => { selectTab('review', true); $('job-list').scrollIntoView({behavior: 'smooth', block: 'nearest'}); };
      box.append(review);
    }
    const edit = el('button', 'Edit preferences', 'text-button');
    edit.type = 'button';
    edit.onclick = editPreferences;
    box.append(edit);
  }
  if (result.warnings?.length) $('message').textContent = result.warnings.join(' ');
  $('export').hidden = false;
  $('export').href = '/api/searches/' + runId + '/export';
}
function finished(status) {
  busy(false);
  renderJobs();
  clearInterval(timer);
  elapsed(lastEventAt || Date.now());
  $('live-dot').classList.add('done');
  $('stage').textContent = status === 'complete' ? 'Search complete' : status === 'interrupted' ? 'Search interrupted' : 'Search stopped';
  if (status !== 'complete') $('result-title').textContent = status === 'interrupted' ? 'Search interrupted' : 'Search stopped';
  loadHistory().catch(() => {});
}
async function watch(id) {
  if (source) source.close();
  runId = id;
  localStorage.setItem('proof-search-id', id);
  matches = new Map(); unknowns = new Map(); exclusions = []; seenEvents = new Set();
  expandedJobs.clear(); finalResult = null; lastEventAt = 0; tab = 'matches'; demoMode = false;
  $('activity-feed').replaceChildren();
  $('activity-panel').open = false;
  $('excluded-section').open = false;
  $('excluded-section').hidden = true;
  $('shortfall').hidden = true;
  $('export').hidden = true;
  $('demo-note').hidden = true;
  $('message').textContent = '';
  $('empty').hidden = true;
  $('output').hidden = false;
  document.body.classList.add('has-run');
  $('live-dot').classList.remove('done');
  $('activity-title').textContent = 'Tool activity';
  $('activity-mode').textContent = '';
  $('stage').textContent = 'Starting search';
  $('result-title').textContent = 'Your shortlist';
  busy(true);
  let run;
  try { run = await api('/api/searches/' + id); }
  catch (error) { $('message').textContent = error.message; finished('failed'); return; }
  requested = run.count;
  $('query').value = run.query || '';
  $('count').value = run.count;
  if ([...$('resume-select').options].some(option => option.value === run.resume_id)) $('resume-select').value = run.resume_id;
  started = new Date(run.created).getTime();
  clearInterval(timer);
  timer = setInterval(elapsed, 1000);
  elapsed(); renderJobs();
  source = new EventSource('/api/searches/' + id + '/events');
  const current = source;
  source.addEventListener('activity', packet => {
    if (source !== current) return;
    const event = JSON.parse(packet.data);
    if (event.type === 'run_started') {
      demoMode = event.data.demo;
      $('demo-note').hidden = !demoMode;
      $('activity-mode').textContent = demoMode ? 'Sample · no API calls' : 'Live';
    }
    addEvent(event);
  });
  source.addEventListener('done', packet => {
    if (source !== current) return;
    const done = JSON.parse(packet.data);
    if (done.result) complete(done.result);
    if (done.error) $('message').textContent = done.error;
    finished(done.status); current.close();
  });
  source.onerror = () => { if (source === current && running) $('stage').textContent = 'Reconnecting…'; };
}
$('search-form').onsubmit = async event => {
  event.preventDefault();
  const resumeId = $('resume-select').value;
  if (!resumeId) { $('resume-status').textContent = 'Attach a résumé to search.'; $('resume-file').focus(); return; }
  $('message').textContent = '';
  busy(true);
  try {
    const run = await api('/api/searches', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({resume_id: resumeId, query: $('query').value, count: Number($('count').value)})});
    await watch(run.id);
  } catch (error) { $('message').textContent = error.message; busy(false); }
};
$('demo-button').onclick = async () => {
  busy(true);
  try {
    const run = await api('/api/demo', {method: 'POST'});
    await loadResumes();
    await watch(run.id);
  } catch (error) { $('message').textContent = error.message; busy(false); }
};
$('new-search').onclick = () => {
  if (source) source.close();
  source = null; runId = null;
  clearInterval(timer);
  localStorage.removeItem('proof-search-id');
  $('output').hidden = true;
  $('empty').hidden = false;
  $('message').textContent = '';
  $('resume-status').textContent = '';
  $('query').value = '';
  $('count').value = 5;
  $('history-menu').open = false;
  document.body.classList.remove('has-run');
  busy(false);
  $('query').focus();
};
async function loadHistory() {
  const rows = await api('/api/searches');
  if (!rows.length) { $('history').replaceChildren(el('p', 'No searches yet.')); return; }
  $('history').replaceChildren(...rows.map(run => {
    const button = el('button', (run.query || 'Résumé search').slice(0, 65) + ' · ' + run.status);
    button.type = 'button';
    button.disabled = running;
    button.onclick = () => { $('history-menu').open = false; watch(run.id); };
    return button;
  }));
}
async function init() {
  try {
    const config = await api('/api/config');
    $('connection').textContent = config.live_ready ? 'Local workspace' : 'Live search needs a Nimble key';
    await loadResumes();
    await loadHistory();
    const id = localStorage.getItem('proof-search-id');
    if (id) await watch(id);
  } catch (error) { $('message').textContent = error.message; }
}
init();
