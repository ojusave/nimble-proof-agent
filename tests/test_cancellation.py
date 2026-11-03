import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from adapters.demo import SAMPLE_RESUME
from adapters.nimble.agent import NimbleAgent
from adapters.nimble.client import NimbleClient
from api.app import create_app
from core.cancellation import CancellationToken, SearchCancelled, stopped_result
from core.models import SearchRequest
from core.settings import Settings
from workflows.job_matcher import JobWorkflow


class CancellationTests(unittest.TestCase):
    def test_partial_result_keeps_received_matches_and_review_separate(self):
        result = stopped_result(SearchRequest('r', count=1), [
            {'type': 'plan_ready', 'data': {'requirements': [{'id': 'R1', 'text': 'Remote'}], 'round': 1}},
            {'type': 'job_matched', 'data': {'job': {'id': 'match'}}},
            {'type': 'job_unknown', 'data': {'job': {'id': 'review'}}},
        ])
        self.assertEqual([j['id'] for j in result['jobs']], ['match'])
        self.assertEqual([j['id'] for j in result['unknowns']], ['review'])
        self.assertTrue(result['incomplete'])

    def test_stop_is_idempotent_preserves_terminal_state_and_prevents_next_call(self):
        entered, release = threading.Event(), threading.Event()
        provider = Mock()
        def search(*args):
            entered.set()
            release.wait(3)
            return [{'url': 'https://employer.example/careers/1', 'title': 'Engineer'}]
        provider.search.side_effect = search
        with tempfile.TemporaryDirectory() as directory, TestClient(create_app(Settings(data_dir=Path(directory)), provider=provider)) as client:
            resume = client.post('/api/resumes', files={'file': ('sample.txt', SAMPLE_RESUME.encode(), 'text/plain')}).json()
            rid = client.post('/api/searches', json={'resume_id': resume['id'], 'query': 'Python'}).json()['id']
            self.assertTrue(entered.wait(2))
            try:
                self.assertEqual(client.post(f'/api/searches/{rid}/stop').json()['status'], 'stopping')
                self.assertEqual(client.post(f'/api/searches/{rid}/stop').json()['status'], 'stopping')
            finally: release.set()
            for _ in range(100):
                value = client.get(f'/api/searches/{rid}').json()
                if value['status'] == 'stopped': break
                time.sleep(.02)
            self.assertEqual(value['status'], 'stopped')
            self.assertTrue(value['result']['incomplete'])
            self.assertEqual(provider.search.call_count, 1)
            provider.extract.assert_not_called()
            provider.structured.assert_not_called()
            events = client.get(f'/api/searches/{rid}/trace').json()['events']
            kinds = [item['type'] for item in events]
            self.assertEqual(kinds.count('run_stopping'), 1)
            self.assertEqual(kinds[-1], 'run_stopped')
            self.assertNotIn('search_completed', kinds)
            self.assertEqual(client.post(f'/api/searches/{rid}/stop').json()['status'], 'stopped')
            exported = client.get(f'/api/searches/{rid}/export').text
            self.assertIn('Stopped early', exported)
            stream = client.post('/api/agent', json={'threadId': rid, 'runId': 'observer', 'forwardedProps': {'search_id': rid}}).text
            self.assertIn('RUN_FINISHED', stream)
            self.assertNotIn('RUN_ERROR', stream)
            self.assertEqual(client.post('/api/searches/missing/stop').status_code, 404)

    def test_stop_during_retrieval_does_not_start_paid_research(self):
        control = CancellationToken()
        extract, reasoner = Mock(), Mock()
        def captured(url):
            control.cancel()
            return 'Python developer opening. ' * 20
        extract.extract.side_effect = captured
        workflow = JobWorkflow(Mock(), extract, reasoner, Settings(), lambda event: None, control.is_cancelled)
        with self.assertRaises(SearchCancelled):
            workflow.screen_batch([{'id': 'a', 'url': 'https://employer.example/jobs/1', 'title': 'Engineer'}], {})
        reasoner.structured.assert_not_called()

    def test_stop_ends_agent_observation_without_creating_or_polling_again(self):
        control = CancellationToken()
        client = Mock()
        client.settings.agent_timeout = 300
        client.request.return_value = {'id': 'run_1', 'web_search_agent_id': 'agent_1', 'status': 'queued'}
        agent = NimbleAgent(client, control)
        with patch.object(agent, 'progress'), self.assertRaises(SearchCancelled):
            agent.structured('task', {}, 'match', lambda event: control.cancel())
        self.assertEqual(client.request.call_count, 1)

    def test_cancelled_transport_never_submits_a_new_request(self):
        control = CancellationToken()
        control.cancel()
        client = NimbleClient(Settings(api_key='fixture-key'), control)
        with patch('httpx.Client') as http, self.assertRaises(SearchCancelled):
            client.request('POST', 'agents/runs', {}, retries=0)
        http.assert_not_called()
