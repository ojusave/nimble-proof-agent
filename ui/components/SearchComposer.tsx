'use client';
import {useRef, useState, type FormEvent} from 'react';
import {ArrowUp, Check, FileText, Info, LoaderCircle, Paperclip, Trash2} from 'lucide-react';
import type {Resume} from '../core/types';

export interface ComposerProps {
  resumes: Resume[]; selected: string; query: string; count: number; disabled: boolean;
  liveReady: boolean; uploading: boolean; status: string;
  onSelect(id: string): void; onQuery(value: string): void; onCount(value: number): void;
  onUpload(file: File): void; onRemove(): void; onSubmit(event: FormEvent): void;
}
export function SearchComposer(props: ComposerProps) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const selected = props.resumes.find(item => item.id === props.selected);
  return <form className={'composer' + (dragging ? ' dragging' : '')} onSubmit={props.onSubmit} aria-label="Job search preferences"
    onDragOver={event => {if (event.dataTransfer.types.includes('Files')) {event.preventDefault(); setDragging(true);}}}
    onDragLeave={event => {if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false);}}
    onDrop={event => {event.preventDefault(); setDragging(false); const file = event.dataTransfer.files[0]; if (file && !props.disabled && !props.uploading) props.onUpload(file);}}>
    {dragging && <div className="drop-indicator"><Paperclip size={24}/>Drop your résumé here</div>}
    <div className="query-field"><label className="sr-only" htmlFor="preferences">What are you looking for? Optional</label>
      <textarea id="preferences" value={props.query} disabled={props.disabled} maxLength={1500} rows={2}
        onChange={event => props.onQuery(event.target.value)} placeholder="Role, location, or what matters to you…"/>
    </div>
    <div className="composer-toolbar"><div className="resume-controls">
      <input ref={input} type="file" className="sr-only" accept=".pdf,.docx,.txt" aria-label="Upload résumé" disabled={props.disabled || props.uploading}
        onChange={event => {const file = event.target.files?.[0]; if (file) props.onUpload(file); event.currentTarget.value = '';}}/>
      <button className="attach-button" type="button" disabled={props.disabled || props.uploading} onClick={() => input.current?.click()}>
        {props.uploading ? <LoaderCircle size={16} className="spin"/> : <Paperclip size={16}/>} {props.uploading ? 'Reading…' : selected ? 'Replace' : 'Attach résumé'}
      </button>
      {!!props.resumes.length && <div className="resume-chip"><FileText size={14}/><select aria-label="Saved résumé" title={selected?.name} value={props.selected} disabled={props.disabled || props.uploading} onChange={event => props.onSelect(event.target.value)}>
        {!props.selected && <option value="">Select a résumé</option>}{props.resumes.map(resume => <option key={resume.id} value={resume.id}>{resume.name}</option>)}
      </select><button className="icon-button" type="button" title="Remove résumé; previous results remain" aria-label="Remove selected résumé" disabled={props.disabled || !selected} onClick={props.onRemove}><Trash2 size={13}/></button></div>}
    </div><div className="submit-controls"><div className="count-control"><input id="result-count" aria-label="Results" type="number" min={1} max={20} required value={props.count} disabled={props.disabled} onChange={event => props.onCount(Number(event.target.value))}/><label htmlFor="result-count">matches</label></div>
      <button className="primary-button search-submit" aria-label="Find jobs" type="submit" disabled={props.disabled || props.uploading || !props.liveReady || !selected} title={!selected ? 'Attach or select a résumé first' : !props.liveReady ? 'Live search needs a configured Nimble key' : 'Find jobs'}>
        <span>Find jobs</span><ArrowUp size={18}/>
      </button></div></div>
    <div className="composer-footnote"><span>PDF, DOCX, TXT · 3 MB</span><details className="upload-info"><summary aria-label="How your résumé is used"><Info size={14}/></summary><p>Selected résumé passages are sent to Nimble for research. Files and search history are saved in this workspace.</p></details>
      {props.status && <span className="upload-status" role="status"><Check size={12}/>{props.status}</span>}</div>
  </form>;
}
