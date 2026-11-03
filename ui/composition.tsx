'use client';
import {useState, type ReactNode} from 'react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {CopilotKitProvider} from '@copilotkit/react-core/v2';
import {createHttpRepository} from './adapters/httpRepository';
import {CopilotConnection} from './adapters/CopilotConnection';
import {SseConnection} from './adapters/SseConnection';

export const repository = createHttpRepository();
const native = process.env.NEXT_PUBLIC_TRACE_TRANSPORT === 'sse';
export const SearchConnection = native ? SseConnection : CopilotConnection;

export function Providers({children}: {children: ReactNode}) {
  const [queryClient] = useState(() => new QueryClient({defaultOptions: {queries: {retry: 1, refetchOnWindowFocus: false}, mutations: {retry: false}}}));
  const content = <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  return native ? content : <CopilotKitProvider runtimeUrl="/api/copilotkit" agentId="proof" enableInspector={false} showDevConsole={false}>{content}</CopilotKitProvider>;
}
