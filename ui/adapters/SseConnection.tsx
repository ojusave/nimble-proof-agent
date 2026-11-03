'use client';
import {useEffect, useState} from 'react';
import {SessionContext, type ConnectionProps} from '../application/SessionContext';
import {mergeEvent} from '../core/session';
import type {ActivityEvent, ConnectionStatus, SearchRun} from '../core/types';

// A working replacement for CopilotKit, selected only in ui/composition.tsx.
export function SseConnection({initialRun, repository, children}: ConnectionProps) {
  const [run, setRun] = useState(initialRun), [events, setEvents] = useState<ActivityEvent[]>([]);
  const [connection, setConnection] = useState<ConnectionStatus>('connecting');
  const [error, setError] = useState(''), [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const stream = new EventSource(repository.eventsUrl(initialRun.id));
    stream.onopen = () => {setConnection('connected'); setError('');};
    stream.addEventListener('activity', packet => setEvents(previous => mergeEvent(previous, JSON.parse(packet.data))));
    stream.addEventListener('state', packet => setRun(JSON.parse(packet.data) as SearchRun));
    stream.addEventListener('done', packet => {setRun(JSON.parse(packet.data) as SearchRun); setConnection('closed'); stream.close();});
    stream.onerror = () => {setConnection('reconnecting'); setError('Connection interrupted. Reconnecting to the saved run.');};
    return () => stream.close();
  }, [initialRun.id, repository, attempt]);
  return <SessionContext.Provider value={{run, events, connection, error, transport: 'Native SSE', reconnect: () => setAttempt(value => value + 1)}}>{children}</SessionContext.Provider>;
}
