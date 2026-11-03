export type RunStatus = 'running' | 'stopping' | 'stopped' | 'complete' | 'failed' | 'interrupted';
export type RequirementCheck = {id: string; requirement: string; status: 'met' | 'conflict' | 'unknown'; evidence: string};
export type Citation = {url?: string; title?: string; excerpts?: string[] | null};
export type Claim = {path?: string; callout?: number; confidence?: string; reasoning?: string; citations?: Citation[]};
export type Research = {run_id?: string; agent_id?: string; trust?: {confidence?: string | number; reasoning?: string; sources?: Citation[]; claims?: Claim[]}};
export type Job = {
  id: string; title: string; company: string; url: string; location: string; fit: string; summary: string;
  strengths: {reason: string; resume_quote: string; job_quote: string}[];
  checks: RequirementCheck[]; gaps: string[]; unknown_requirements?: string[];
  open_evidence?: string; checked_at?: string; rank?: number; provisional?: boolean; sample_listing?: string;
  research?: Research;
  evidence?: {source_characters: number; selected_characters: number; scanned_characters: number; scan_limited: boolean; passages: {id: string; start: number; end: number; text: string}[]};
};
export type Exclusion = {url: string; title: string; reason: string; category?: string};
export type SearchResult = {jobs: Job[]; unknowns: Job[]; excluded: Exclusion[]; requested: number; rounds: number; shortfall: number; warnings: string[]; mode: string; next_question?: string; requirements: {id: string; text: string}[]};
export type SearchRun = {id: string; created: string; resume_id: string; query: string; count: number; status: RunStatus; result: SearchResult | null; error: string | null};
export type RecentRun = Pick<SearchRun, 'id' | 'created' | 'query' | 'count' | 'status'>;
export type Resume = {id: string; name: string; created: string; characters: number};
export type Config = {live_ready: boolean; framework: string; default_count: number; max_rounds: number};
// Event payloads remain extensible across providers. Known UI result fields are typed above.
export type ActivityEvent = {id: string; seq: number; at: string; type: string; step: string; message: string; data: Record<string, any>};
export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'closed';
