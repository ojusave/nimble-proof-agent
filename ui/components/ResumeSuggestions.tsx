'use client';
import {useState} from 'react';
import {Download} from 'lucide-react';
import type {ResumeProposal} from '../core/types';
import {SourceLink} from './shared';

export function ResumeSuggestions({proposal,onDraft}: {proposal: ResumeProposal; onDraft(edits: number[]): Promise<{markdown: string}>}) {
  const [selected,setSelected]=useState<number[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function download() {
    setBusy(true);setError('');
    try {
      const {markdown}=await onDraft(selected);
      const url=URL.createObjectURL(new Blob([markdown],{type:'text/markdown'}));
      const link=document.createElement('a');link.href=url;link.download='proof-tailored-resume.md';link.click();
      setTimeout(() => URL.revokeObjectURL(url),1000);
    } catch (cause) {setError(cause instanceof Error ? cause.message : 'Could not prepare the draft.');}
    finally {setBusy(false);}
  }
  return <section className="resume-suggestions"><h4>Résumé suggestions from your public work</h4>
    <p className="evidence-note">Review the wording and confirm it accurately describes your contribution. Selected additions go into a separate Markdown draft.</p>
    {proposal.edits.map((edit,index) => <div className="resume-suggestion" key={index}>
      <p>{edit.wording}</p><p className="muted">{edit.reason}</p>
      <div className="quote-pair"><div><span className="eyebrow">Public work</span><blockquote>{edit.source_quote}</blockquote><SourceLink url={edit.source_url}>Check source and attribution</SourceLink></div><div><span className="eyebrow">Job requirement</span><blockquote>{edit.job_quote}</blockquote></div></div>
      <label><input type="checkbox" checked={selected.includes(index)} onChange={event => setSelected(previous => event.target.checked ? [...previous,index] : previous.filter(value => value!==index))}/>This accurately describes my work; include this addition.</label>
    </div>)}
    {!proposal.edits.length && <p className="muted">No supported additions were established for this role.</p>}
    {!!proposal.remaining_gaps?.length && <><h4>Still not established</h4><ul className="gap-list">{proposal.remaining_gaps.map((gap,index) => <li key={index}>{gap}</li>)}</ul></>}
    {!!proposal.edits.length && <button className="secondary-button" disabled={!selected.length || busy} onClick={download}><Download size={14}/>{busy ? 'Preparing…' : 'Download résumé draft (.md)'}</button>}
    {(error || proposal.error) && <p role="alert" className="notice error">{error || proposal.error}</p>}
  </section>;
}
