"""Translate recorded domain events into AG-UI. No workflow or provider imports.

Observing/reconnecting is read-only: it never creates another paid search.
"""
import json


def encode(kind, **fields):
    return 'data: ' + json.dumps({'type': kind, **fields}) + '\n\n'


class AgentEventBridge:
    def __init__(self):
        self.calls = {}
        self.candidates = {}
        self.demo = False
        self.last_search = None

    def activity(self, item):
        # Preserve the original timestamp, sequence, source, and candidate IDs.
        yield encode('CUSTOM', name='proof.activity', value=item)
        data = item.get('data', {})
        kind, step = item['type'], item['step']
        if kind == 'run_started':
            self.demo = bool(data.get('demo'))
        if kind == 'search_results':
            self.candidates.update({c['id']: c['url'] for c in data.get('candidates', [])})
        identity = data.get('query') if step == 'search' else (
            data.get('candidate_id') or next(iter(data.get('candidate_ids', [])), None))
        identity = identity or data.get('url')
        if step == 'search' and data.get('query'):
            self.last_search = data['query']
        if step == 'search' and not identity:
            identity = self.last_search
        key = (step, identity)
        if kind == 'tool_started':
            call_id = 'call_' + item['id']
            self.calls[key] = call_id
            name = {'search': 'nimble_search', 'extract': 'nimble_extract', 'match': 'nimble_agent',
                    'profile':'nimble_extract' if data.get('tool')=='Nimble Extract API' else 'nimble_applicant_research',
                    'tailor':'nimble_role_resume_research'}.get(step, step)
            if self.demo:
                name = 'sample_' + name
            args = {'query': data['query']} if 'query' in data else {
                'url': data.get('url') or self.candidates.get(identity), 'candidate_id': identity}
            yield encode('TOOL_CALL_START', toolCallId=call_id, toolCallName=name)
            yield encode('TOOL_CALL_ARGS', toolCallId=call_id, delta=json.dumps(args))
            # AG-UI END closes the argument stream, not the provider execution.
            yield encode('TOOL_CALL_END', toolCallId=call_id)
        elif kind in ('search_results', 'extraction_ready', 'research_completed', 'tool_failed',
                      'profile_source_checked','profile_research_completed','profile_research_failed','resume_proposals_ready','tailoring_failed'):
            call_id = self.calls.pop(key, None)
            if call_id:
                output = {'message': item['message'], **data}
                yield encode('TOOL_CALL_RESULT', messageId='result_' + item['id'],
                             toolCallId=call_id, role='tool', content=json.dumps(output))
        elif kind == 'job_excluded':
            identity = data.get('candidate_id') or next((key for key, url in self.candidates.items() if url == data.get('url')), None)
            for failed_step in ('extract', 'match'):
                call_id = self.calls.pop((failed_step, identity), None)
                if call_id:
                    yield encode('TOOL_CALL_RESULT', messageId='result_' + call_id,
                                 toolCallId=call_id, role='tool', content=json.dumps({'status': 'no_result', 'message': data.get('reason', item['message'])}))

    def finish(self):
        # A missing result is explicit, never represented as a successful call.
        for call_id in self.calls.values():
            yield encode('TOOL_CALL_RESULT', messageId='unresolved_' + call_id,
                         toolCallId=call_id, role='tool',
                         content=json.dumps({'status': 'no_result', 'message': 'No successful provider output was recorded. See the activity outcome.'}))
        self.calls.clear()
