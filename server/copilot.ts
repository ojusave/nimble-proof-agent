import { HttpAgent } from '@ag-ui/client';
import { CopilotRuntime, InMemoryAgentRunner, createCopilotRuntimeHandler } from '@copilotkit/runtime/v2';
import { backendUrl } from './backend';

// Transport only. Search creation, data, validation, and persistence remain Python-owned.
const runtime = new CopilotRuntime({
  // The HTTP boundary authenticates access to one shared workspace, not separate accounts.
  identifyUser: () => ({id: 'proof-workspace', name: 'Proof workspace'}),
  agents: {proof: new HttpAgent({url: backendUrl + '/api/agent'})},
  runner: new InMemoryAgentRunner(),
});
export const copilotHandler = createCopilotRuntimeHandler({runtime, basePath: '/api/copilotkit'});
