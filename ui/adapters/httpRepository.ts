import type {SearchRepository} from '../core/ports';
import {uploadResume} from './uploadStream';

export function createHttpRepository(base = '/api/backend'): SearchRepository {
  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(base + path, {...options, cache: 'no-store'});
    let value;
    try { value = await response.json(); } catch { throw new Error('The search service returned an unreadable response. Try reconnecting.'); }
    if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'The request could not be completed. Check the form and try again.');
    return value as T;
  }
  const json = (value: unknown) => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value)});
  return {
    config: () => request('/config'), resumes: () => request('/resumes'), history: () => request('/searches'),
    upload: (file,onProgress) => uploadResume(base+'/resumes',file,onProgress),
    removeResume: id => request('/resumes/' + encodeURIComponent(id), {method: 'DELETE'}),
    start: value => request('/searches', json(value)), sample: () => request('/demo', {method: 'POST'}),
    resumeDraft: (id,jobId,edits) => request('/searches/' + encodeURIComponent(id) + '/resume-draft',json({job_id:jobId,edits})),
    tailor: (id,jobId) => request('/searches/' + encodeURIComponent(id) + '/tailor',json({job_id:jobId})),
    run: id => request('/searches/' + encodeURIComponent(id)),
    stop: id => request('/searches/' + encodeURIComponent(id) + '/stop', {method: 'POST'}),
    exportUrl: id => base + '/searches/' + encodeURIComponent(id) + '/export',
    traceUrl: id => base + '/searches/' + encodeURIComponent(id) + '/trace',
    eventsUrl: id => base + '/searches/' + encodeURIComponent(id) + '/events',
  };
}
