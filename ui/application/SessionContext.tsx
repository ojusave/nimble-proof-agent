'use client';
import {createContext, useContext, type ReactNode} from 'react';
import type {SearchSession, SearchRepository} from '../core/ports';
import type {SearchRun} from '../core/types';

export const SessionContext = createContext<SearchSession | null>(null);
export type ConnectionProps = {initialRun: SearchRun; repository: SearchRepository; children: ReactNode};
export function useSearchSession() {
  const session = useContext(SessionContext);
  if (!session) throw new Error('SearchSession provider is missing.');
  return session;
}
