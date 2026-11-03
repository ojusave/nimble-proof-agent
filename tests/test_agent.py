import json
import tempfile
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from api.app import create_app
from core.settings import Settings
from adapters.transport.ag_ui import AgentEventBridge


class AgentTransportTests(unittest.TestCase):
    def test_completed_search_replays_through_agui_without_creating_a_new_search(self):
        with tempfile.TemporaryDirectory() as directory, TestClient(create_app(Settings(data_dir=Path(directory)))) as client:
            rid = client.post('/api/demo').json()['id']
            for _ in range(100):
                if client.get('/api/searches/' + rid).json()['status'] != 'running': break
                time.sleep(.02)
            body = {'threadId': rid, 'runId': 'observer-1', 'forwardedProps': {'search_id': rid}, 'messages': [], 'tools': [], 'context': [], 'state': {}}
            response = client.post('/api/agent', json=body)
            self.assertEqual(response.status_code, 200)
            packets = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
            self.assertEqual(packets[0]['type'], 'RUN_STARTED')
            self.assertEqual(packets[-1]['type'], 'RUN_FINISHED')
            snapshot = [p for p in packets if p['type'] == 'STATE_SNAPSHOT'][-1]
            self.assertEqual(snapshot['snapshot']['search']['result']['shortfall'], 1)
            activity = [p['value'] for p in packets if p['type'] == 'CUSTOM' and p['name'] == 'proof.activity']
            self.assertEqual(activity, client.app.state.repository.events(rid))
            starts = [p for p in packets if p['type'] == 'TOOL_CALL_START']
            results = [p for p in packets if p['type'] == 'TOOL_CALL_RESULT']
            self.assertTrue(all(p['toolCallName'].startswith('sample_') for p in starts))
            self.assertEqual({p['toolCallId'] for p in starts}, {p['toolCallId'] for p in results})
            client.post('/api/agent', json={**body, 'runId': 'observer-2'})
            self.assertEqual(len(client.get('/api/searches').json()), 1)
            trace = client.get('/api/searches/' + rid + '/trace').json()
            self.assertEqual(trace['events'], activity)
            self.assertNotIn('api_key', json.dumps(trace))
            self.assertEqual(client.post('/api/agent', json={**body, 'forwardedProps': {'search_id': 'missing'}}).status_code, 404)

    def test_failed_search_has_an_error_event_not_success(self):
        with tempfile.TemporaryDirectory() as directory, TestClient(create_app(Settings(data_dir=Path(directory)))) as client:
            repo = client.app.state.repository
            from core.models import SearchRequest
            resume=repo.save_resume('fixture.txt',b'Fixture resume','Fixture resume')
            rid = repo.create(SearchRequest(resume['id']))
            repo.finish(rid, error='Nimble returned HTTP 402.')
            response = client.post('/api/agent', json={'threadId': rid, 'runId': 'watch', 'forwardedProps': {'search_id': rid}})
            self.assertIn('RUN_ERROR', response.text)
            self.assertIn('Nimble returned HTTP 402.', response.text)
            self.assertNotIn('RUN_FINISHED', response.text)

    def test_interleaved_calls_keep_their_provider_identity(self):
        bridge = AgentEventBridge()
        def item(kind, step, identity, **data):
            return {'id': identity + kind, 'seq': 1, 'at': '2026-11-02T00:00:00Z', 'type': kind, 'step': step, 'message': kind, 'data': {'candidate_id': identity, **data}}
        outputs = []
        for event in [item('tool_started', 'extract', 'a'), item('tool_started', 'extract', 'b'), item('extraction_ready', 'extract', 'b'), item('job_excluded', 'match', 'a', reason='Source unavailable')]:
            outputs.extend(json.loads(line[6:]) for line in bridge.activity(event))
        results = [p for p in outputs if p['type'] == 'TOOL_CALL_RESULT']
        self.assertEqual(results[0]['toolCallId'], 'call_btool_started')
        self.assertEqual(results[1]['toolCallId'], 'call_atool_started')
        self.assertIn('Source unavailable', results[1]['content'])
