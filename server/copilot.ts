import { HttpAgent } from '@ag-ui/client';
import { CopilotRuntime, InMemoryAgentRunner, createCopilotRuntimeHandler } from '@copilotkit/runtime/v2';
import { backendUrl } from './backend';
import {workspaceHeader, workspaceId} from './workspace';

// Transport only. Search creation, data, validation, and persistence remain Python-owned.
const runtime = new CopilotRuntime({
  identifyUser: request => ({id: workspaceId(request), name: 'Browser workspace'}),
  agents: ({request}) => ({proof: new HttpAgent({url: backendUrl + '/api/agent',
    headers: {[workspaceHeader]: workspaceId(request)}})}),
  runner: new InMemoryAgentRunner(),
});
export const copilotHandler = createCopilotRuntimeHandler({runtime, basePath: '/api/copilotkit'});
