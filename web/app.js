const $ = id => document.getElementById(id);
let active = null;
let generation = 0;
const node = (tag, text, className) => {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
};
function sourceLink(label, url) {
  const a = node('a', label);
  try { if (new URL(url).protocol !== 'https:') return node('span', label); }
  catch { return node('span', label); }
  a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
}
async function api(path, options) {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Request failed.');
  return value;
}
function busy(value) {
  $('run-button').disabled = value; $('demo-button').disabled = value;
  $('run-button').textContent = value ? 'Investigating…' : 'Start research ↗';
}
async function history() {
  const rows = await api('/api/runs');
  if (!rows.length) return;
  $('history').replaceChildren(...rows.map(row => {
    const button = node('button', (row.mode === 'demo' ? 'DEMO · ' : '') + row.question.slice(0, 75));
    button.onclick = () => watch(row.id); return button;
  }));
}
function render(run) {
  $('run-view').hidden = false;
  $('run-state').textContent = run.status;
  $('mode-note').textContent = run.mode === 'demo'
    ? 'SYNTHETIC DEMO — Fictional companies, scripted model, no live API calls.'
    : 'LIVE RESEARCH — Nimble supplies the evidence. Quote matching checks provenance, not truth.';
  $('trace').replaceChildren(...run.events.map(event => {
    const detail = event.detail;
    const title = {start:'Investigation started',search:'Searched the live web',read:'Read source ' + detail.source_id,finish:'Evidence checks passed',tool_error:'Tool returned an error'}[event.type] || event.type;
    const item = node('li', run.mode === 'demo' && event.type === 'search' ? 'Searched synthetic fixtures' : title);
    item.append(node('small', detail.query || detail.url || detail.error || (event.type === 'finish' ? detail.findings + ' findings with matching quotations' : detail.question || '')));
    return item;
  }));
  if (run.error) $('message').textContent = run.error;
  if (!run.result) return;
  const {brief, sources} = run.result;
  $('run-title').textContent = brief.title;
  $('sources').replaceChildren(...sources.map(source => {
    const box = node('div'); box.append(sourceLink(source.id + ' · ' + source.title, source.url));
    box.append(node('small', source.read ? 'Full page read' : 'Search result only')); return box;
  }));
  const body = [node('h3', brief.title), node('p', brief.summary)];
  for (const finding of brief.findings) {
    const box = node('div', undefined, 'finding');
    box.append(node('p', finding.claim), node('blockquote', finding.quote));
    const source = sources.find(s => s.id === finding.source_id);
    if (source) box.append(sourceLink('[' + source.id + '] View source ↗', source.url));
    body.push(box);
  }
  body.push(node('h4', 'Gaps & limitations'));
  const gaps = node('ul'); brief.gaps.forEach(gap => gaps.append(node('li', gap))); body.push(gaps);
  $('brief').replaceChildren(...body);
  $('download').href = '/api/runs/' + run.id + '/markdown';
  $('download').download = 'proof-brief.md'; $('download').hidden = false;
}
async function watch(id) {
  active = id; const mine = ++generation;
  $('message').textContent = ''; $('run-title').textContent = 'Following the evidence';
  $('brief').replaceChildren(node('p', 'Waiting for the evidence-backed brief…', 'muted'));
  $('sources').replaceChildren(); $('download').hidden = true; busy(true);
  try {
    while (mine === generation) {
      const run = await api('/api/runs/' + id);
      if (mine !== generation) return;
      render(run);
      if (run.status !== 'running') break;
      await new Promise(resolve => setTimeout(resolve, 800));
    }
  } catch (error) { if (mine === generation) $('message').textContent = error.message; }
  finally { if (mine === generation) { busy(false); history().catch(() => {}); } }
}
async function start(mode) {
  $('message').textContent = ''; busy(true);
  try {
    const run = await api('/api/runs', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('question').value,mode})});
    await watch(run.id);
  } catch (error) { $('message').textContent = error.message; busy(false); }
}
$('research-form').onsubmit = event => { event.preventDefault(); start('live'); };
$('demo-button').onclick = () => start('demo');
api('/api/config').then(config => { $('connection').textContent = config.live_ready ? '● Live APIs configured' : '○ Demo ready · live keys needed'; }).catch(error => { $('message').textContent = error.message; });
history().catch(error => { $('message').textContent = error.message; });
