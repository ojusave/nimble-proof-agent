'use client';
import {useRef, type FormEvent} from 'react';
import {ArrowUpRight, Check, FileText, LoaderCircle, Paperclip, Trash2} from 'lucide-react';
import type {Resume} from '../core/types';

export interface ComposerProps {
  resumes: Resume[]; selected: string; query: string; count: number; disabled: boolean;
  liveReady: boolean; uploading: boolean; status: string;
  onSelect(id: string): void; onQuery(value: string): void; onCount(value: number): void;
  onUpload(file: File): void; onRemove(): void; onSubmit(event: FormEvent): void;
}
export function SearchComposer(props: ComposerProps) {
  const input = useRef<HTMLInputElement>(null);
  const selected = props.resumes.find(item => item.id === props.selected);
  return <form className="composer" onSubmit={props.onSubmit} aria-label="Job search preferences">
    <div className="query-field"><label htmlFor="preferences">What are you looking for? <span>Optional</span></label>
      <textarea id="preferences" value={props.query} disabled={props.disabled} maxLength={1500} rows={2}
        onChange={event => props.onQuery(event.target.value)} placeholder="Developer advocate; remote; US; Python…"/>
    </div>
    <div className="composer-toolbar"><div className="resume-controls">
      <input ref={input} type="file" className="sr-only" accept=".pdf,.docx,.txt" aria-label="Upload résumé" disabled={props.disabled || props.uploading}
        onChange={event => {const file = event.target.files?.[0]; if (file) props.onUpload(file); event.currentTarget.value = '';}}/>
      <button className="attach-button" type="button" disabled={props.disabled || props.uploading} onClick={() => input.current?.click()}>
        {props.uploading ? <LoaderCircle size={16} className="spin"/> : <Paperclip size={16}/>} {props.uploading ? 'Reading résumé…' : selected ? 'Replace' : 'Attach résumé'}
      </button>
      {!!props.resumes.length && <div className="resume-chip"><FileText size={14}/><select aria-label="Saved résumé" title={selected?.name} value={props.selected} disabled={props.disabled || props.uploading} onChange={event => props.onSelect(event.target.value)}>
        {!props.selected && <option value="">Select a résumé</option>}{props.resumes.map(resume => <option key={resume.id} value={resume.id}>{resume.name}</option>)}
      </select><button className="icon-button" type="button" title="Remove résumé; previous results remain" aria-label="Remove selected résumé" disabled={props.disabled || !selected} onClick={props.onRemove}><Trash2 size={13}/></button></div>}
    </div><div className="submit-controls"><label htmlFor="result-count">Results</label><input id="result-count" type="number" min={1} max={20} required value={props.count} disabled={props.disabled} onChange={event => props.onCount(Number(event.target.value))}/>
      <button className="primary-button" type="submit" disabled={props.disabled || props.uploading || !props.liveReady} title={!props.liveReady ? 'Live search needs a configured Nimble key' : undefined}>
        {props.disabled ? 'Please wait' : 'Find jobs'}<ArrowUpRight size={17}/>
      </button></div></div>
    <div className="composer-footnote"><span>PDF, DOCX or TXT · up to 3 MB. Selected résumé passages are sent for live research.</span>
      {props.status && <span className="upload-status" role="status"><Check size={12}/>{props.status}</span>}</div>
  </form>;
}
