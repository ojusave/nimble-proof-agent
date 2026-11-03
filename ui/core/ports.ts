import type {Config, Resume, RecentRun, SearchRun, ActivityEvent, ConnectionStatus} from './types';

export interface SearchRepository {
  config(): Promise<Config>;
  resumes(): Promise<Resume[]>;
  history(): Promise<RecentRun[]>;
  upload(file: File): Promise<Resume>;
  removeResume(id: string): Promise<void>;
  start(input: {resume_id: string; query: string; count: number}): Promise<{id: string}>;
  sample(): Promise<{id: string}>;
  stop(id: string): Promise<SearchRun>;
  run(id: string): Promise<SearchRun>;
  exportUrl(id: string): string;
  traceUrl(id: string): string;
  eventsUrl(id: string): string;
}

export interface SearchSession {
  run: SearchRun;
  events: ActivityEvent[];
  connection: ConnectionStatus;
  error: string;
  transport: string;
  reconnect(): void;
}
