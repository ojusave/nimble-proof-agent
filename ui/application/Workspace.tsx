'use client';
import {useCallback, useEffect, useRef, useState, type FormEvent} from 'react';
import {useRouter, useSearchParams} from 'next/navigation';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {ArrowRight, Check, ChevronDown, Clock3, FileSearch, ListTree, LoaderCircle, Plus, RefreshCw} from 'lucide-react';
import {repository, SearchConnection} from '../composition';
import {SearchComposer} from '../components/SearchComposer';
import {RunDashboard} from '../components/RunDashboard';
import {Badge} from '../components/shared';

export function Workspace() {
  const router = useRouter(), params = useSearchParams(), queryClient = useQueryClient();
  const runId = params.get('run');
  const config = useQuery({queryKey: ['config'], queryFn: repository.config});
  const resumes = useQuery({queryKey: ['resumes'], queryFn: repository.resumes});
  const history = useQuery({queryKey: ['history'], queryFn: repository.history});
  const search = useQuery({queryKey: ['run', runId], queryFn: () => repository.run(runId!), enabled: !!runId});
  const [selected, setSelected] = useState(''), [query, setQuery] = useState(''), [count, setCount] = useState(5);
  const [error, setError] = useState(''), [status, setStatus] = useState('');
  const [uploading, setUploading] = useState(false), [starting, setStarting] = useState(false), [active, setActive] = useState(false);
  const [briefOpen, setBriefOpen] = useState(!runId);
  const lock = useRef(false), brief = useRef<HTMLDetailsElement>(null);
  const ready = !!config.data && !!resumes.data && !!history.data;
  const busy = active || starting || uploading;
  const updateStatus = useCallback((value: boolean) => setActive(value), []);
  const navigate = useCallback((id: string, replace = false) => {
    (replace ? router.replace : router.push)(`/?run=${encodeURIComponent(id)}`);
  }, [router]);
  useEffect(() => {
    if (!search.data) return;
    setQuery(search.data.query); setCount(search.data.count); setSelected(search.data.resume_id);
    setActive(['running', 'stopping'].includes(search.data.status)); setBriefOpen(false);
  }, [search.data?.id]);
  async function refresh() {await Promise.all([config.refetch(), resumes.refetch(), history.refetch()]);}
  async function upload(file: File) {
    if (file.size > 3 * 1024 * 1024) {setError('Choose a résumé smaller than 3 MB.'); return;}
    if (busy) return;
    setUploading(true); setError(''); setStatus('');
    try {const resume = await repository.upload(file); await queryClient.invalidateQueries({queryKey: ['resumes']}); setSelected(resume.id); setStatus('Résumé ready');}
    catch (cause) {setError(message(cause));} finally {setUploading(false);}
  }
  async function remove() {
    if (busy || !selected) return;
    try {await repository.removeResume(selected); setSelected(''); await queryClient.invalidateQueries({queryKey: ['resumes']}); setStatus('Removed. Past results remain.');}
    catch (cause) {setError(message(cause));}
  }
  async function start(sample = false) {
    if (lock.current || busy) return;
    if (!sample && !selected) {setError('Attach or select a résumé first.'); return;}
    lock.current = true; setStarting(true); setError(''); setStatus('');
    try {
      const run = sample ? await repository.sample() : await repository.start({resume_id: selected, query, count});
      await queryClient.invalidateQueries({queryKey: ['resumes']});
      navigate(run.id); setBriefOpen(false);
    } catch (cause) {setError(message(cause));}
    finally {lock.current = false; setStarting(false);}
  }
  function edit() {setBriefOpen(true); requestAnimationFrame(() => {brief.current?.scrollIntoView({block: 'center', behavior: 'smooth'}); document.getElementById('preferences')?.focus();});}
  function newSearch() {router.push('/'); setSelected(''); setQuery(''); setCount(5); setActive(false); setBriefOpen(true); setError(''); setStatus('');}
  const loadError = config.error || resumes.error || history.error;
  return <>
    <a className="skip-link" href="#main">Skip to search</a>
    <header className="app-header"><a className="brand" href="/" aria-label="Proof home"><span aria-hidden="true">p</span>proof<small>jobs, with evidence</small></a><nav aria-label="Workspace navigation">
      <details className="history-menu"><summary><Clock3 size={15}/>History<ChevronDown size={13}/></summary><div className="history-popover"><h3>Recent searches</h3>{history.data?.length ? history.data.map(run => <button key={run.id} disabled={active} onClick={event => {event.currentTarget.closest('details')?.removeAttribute('open'); navigate(run.id);}}><span>{run.query || 'Résumé search'}</span><small>{new Date(run.created).toLocaleDateString(undefined, {month: 'short', day: 'numeric'})} · {run.status === 'complete' ? 'Completed' : run.status}</small></button>) : <p>No searches yet.</p>}</div></details>
      <button className="secondary-button" onClick={newSearch} disabled={busy}><Plus size={15}/>New search</button>
    </nav></header>
    <main id="main" className={'workspace ' + (runId ? 'has-run' : 'welcome')}>
      <div className="intro"><p className="eyebrow">A CLEARER SHORTLIST</p><h1>{runId ? 'Find jobs that fit your résumé.' : <>Your next role.<br/>The evidence to explore it.</>}</h1>{!runId && <p className="intro-copy">Bring your experience. Find openings, check the requirements,<br className="desktop-break"/> and see exactly what supports each recommendation.</p>}</div>
      {loadError && <div className="notice error" role="alert"><p>{message(loadError)}</p><button className="text-button" onClick={refresh}><RefreshCw size={14}/>Retry connection</button></div>}
      <details className={'search-brief ' + (!runId ? 'initial' : '')} open={briefOpen} onToggle={event => setBriefOpen(event.currentTarget.open)} ref={brief}>
        <summary><div><span className="eyebrow">SEARCH BRIEF</span><strong>{query || 'Based on your résumé'}</strong><small>{resumes.data?.find(resume => resume.id === selected)?.name || 'Saved résumé'} · {count} requested matches</small></div><span>{briefOpen ? 'Hide' : active ? 'View' : 'Edit'}<ChevronDown size={14}/></span></summary>
        <SearchComposer resumes={resumes.data || []} selected={selected} query={query} count={count} disabled={!ready || busy} liveReady={!!config.data?.live_ready} uploading={uploading} status={status}
          onSelect={setSelected} onQuery={setQuery} onCount={setCount} onUpload={upload} onRemove={remove} onSubmit={(event: FormEvent) => {event.preventDefault(); void start();}}/>
      </details>
      {error && <div className="notice error" role="alert">{error}</div>}
      {!runId && <><div className="sample-row"><span>{config.data && !config.data.live_ready ? 'Live search needs a Nimble key. Explore a sample first.' : 'Just looking around?'}</span><button className="text-button" onClick={() => start(true)} disabled={!ready || busy}>{starting ? <LoaderCircle className="spin" size={15}/> : null}Try a sample<ArrowRight size={15}/></button></div>
        <div className="welcome-guide">{[{Icon: FileSearch, title: 'Start with your experience', copy: 'Upload a résumé and add the things that matter to you.'}, {Icon: ListTree, title: 'Follow the actual work', copy: 'See which pages were read and how each opening was checked.'}, {Icon: Check, title: 'Keep uncertainty visible', copy: 'Missing evidence goes to review. Your requirements stay yours.'}].map(({Icon, title, copy}, index) => <div key={title}><span className="guide-icon"><Icon size={18}/></span><small>0{index + 1}</small><h2>{title}</h2><p>{copy}</p></div>)}</div></>}
      {runId && search.isPending && <div className="loading-run" role="status"><LoaderCircle className="spin" size={20}/>Opening the saved search…</div>}
      {runId && search.error && <div className="notice error" role="alert"><p>{message(search.error)}</p><button className="text-button" onClick={newSearch}>Start a new search<ArrowRight size={14}/></button></div>}
      {search.data && runId && <SearchConnection key={runId} initialRun={search.data} repository={repository}><RunDashboard repository={repository} onEdit={edit} onStatus={updateStatus}/></SearchConnection>}
      <footer className="workspace-footer"><a href="https://github.com/ojusave/nimble-proof-agent" target="_blank" rel="noopener noreferrer">Source code ↗</a><span>Saved in this workspace. Evidence stays open to review.</span></footer>
    </main>
  </>;
}
function message(cause: unknown) {return cause instanceof Error ? cause.message : 'Something went wrong. Please try again.';}
