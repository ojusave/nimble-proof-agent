// Derived from recorded events, never from how long the screen has been open.
type RecordedCall = {
  status: string;
  updates: {event: string; step?: string; at?: string}[];
  output: {page?: unknown; research?: unknown};
};
export function recordedOperations(call: RecordedCall) {
  return (['extract', 'match'] as const).flatMap(step => {
    const started = call.updates.find(event => event.event === 'tool_started' && event.step === step);
    if (!started) return [];
    const returned = call.updates.find(event => event.event === (step === 'extract' ? 'extraction_ready' : 'research_completed'));
    const result = step === 'extract' ? call.output.page : call.output.research;
    return [{step, name: step === 'extract' ? 'Extract page' : 'Research opening', started: started.at, ended: returned?.at,
      status: result ? 'Output received' : call.status === 'active' ? 'Waiting for output' : 'No output recorded'}];
  });
}
