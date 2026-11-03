'use client';
import {useEffect, useRef, useState} from 'react';
import {useAgent} from '@copilotkit/react-core/v2/headless';
import {SessionContext, type ConnectionProps} from '../application/SessionContext';
import {mergeEvent} from '../core/session';
import type {ActivityEvent, ConnectionStatus, SearchRun} from '../core/types';

export function CopilotConnection({initialRun, children}: ConnectionProps) {
  const {agent, isReady} = useAgent({agentId: 'view-' + initialRun.id, runtimeAgentId: 'proof', threadId: initialRun.id});
  const [run, setRun] = useState(initialRun);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [connection, setConnection] = useState<ConnectionStatus>('connecting');
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const pending = useRef<Promise<unknown> | null>(null);

  useEffect(() => {
    if (!isReady) return;
    let disposed = false, terminal = false, retry: ReturnType<typeof setTimeout> | undefined;
    const subscription = agent.subscribe({
      onRunStartedEvent: () => { if (!disposed) {setConnection('connected'); setError('');} },
      onCustomEvent: ({event}) => {
        if (!disposed && event.name === 'proof.activity') setEvents(previous => mergeEvent(previous, event.value as ActivityEvent));
      },
      onStateSnapshotEvent: ({event}) => {
        const value = (event.snapshot as {search?: SearchRun})?.search;
        if (!disposed && value?.id === initialRun.id) setRun(value);
      },
      onRunFinishedEvent: () => { terminal = true; if (!disposed) setConnection('closed'); },
      onRunErrorEvent: ({event}) => {
        if (event.code?.startsWith('SEARCH_')) terminal = true;
        if (!disposed) setError(event.message);
      },
    });
    async function observe() {
      // React StrictMode and reconnects must not overlap runs on one agent instance.
      await pending.current?.catch(() => {});
      if (disposed) return;
      setConnection(attempt ? 'reconnecting' : 'connecting');
      const task = agent.runAgent({runId: crypto.randomUUID(), forwardedProps: {search_id: initialRun.id}});
      pending.current = task;
      try {
        await task;
        if (!terminal && !disposed) throw new Error('The activity stream ended before completion.');
      } catch (cause) {
        if (!disposed && !terminal) {
          setError(cause instanceof Error ? cause.message : 'The activity connection was interrupted.');
          setConnection('reconnecting');
          retry = setTimeout(() => setAttempt(value => value + 1), Math.min(15000, 1500 * 2 ** Math.min(attempt, 4)));
        }
      } finally {
        if (!disposed && terminal) setConnection('closed');
      }
    }
    void observe();
    return () => {disposed = true; clearTimeout(retry); subscription.unsubscribe(); agent.abortRun();};
  }, [agent, isReady, initialRun.id, attempt]);

  return <SessionContext.Provider value={{run, events, connection, error, transport: 'CopilotKit · AG-UI', reconnect: () => setAttempt(value => value + 1)}}>{children}</SessionContext.Provider>;
}
