import threading
import unittest
from unittest.mock import patch

import httpx

from adapters.nimble.agent import NimbleAgent
from adapters.nimble.client import NimbleClient, ProviderError
from adapters.nimble.extract import NimbleExtract
from adapters.nimble.search import NimbleSearch
from composition import build_services
from core.settings import Settings


class ProviderTests(unittest.TestCase):
    def client(self, **kwargs):
        return NimbleClient(Settings(api_key='fixture-key', **kwargs))

    def test_search_and_extract_contracts_and_full_listing(self):
        client = self.client()
        listing = 'Navigation. ' * 3000 + 'Apply for this Python job.'
        with patch.object(client, 'request', side_effect=[
            {'results': [{'url': 'https://example.org/job'}, None]},
            {'status': 'success', 'data': {'markdown': listing}},
        ]) as request:
            self.assertEqual(len(NimbleSearch(client).search('Python jobs', 8)), 1)
            self.assertEqual(NimbleExtract(client).extract('https://example.org/job'), listing)
        self.assertEqual(request.call_args_list[0].args, ('POST', 'search', {
            'query': 'Python jobs', 'max_results': 8, 'search_depth': 'standard', 'output_format': 'markdown'}))
        self.assertEqual(request.call_args_list[1].args, ('POST', 'extract', {
            'url': 'https://example.org/job', 'formats': ['markdown'], 'render': True}))

    def test_invalid_endpoint_responses_fail_explicitly(self):
        client = self.client()
        for adapter, method, payload in [
            (NimbleSearch(client), 'search', {'results': {}}),
            (NimbleExtract(client), 'extract', {'status': 'success', 'data': {'markdown': ''}}),
        ]:
            with self.subTest(method=method), patch.object(client, 'request', return_value=payload), self.assertRaises(ProviderError):
                getattr(adapter, method)(*(['query', 2] if method == 'search' else ['https://example.org/job']))

    def test_research_polls_once_created_and_retains_trust(self):
        client = self.client(); adapter = NimbleAgent(client)
        trust = {'confidence': .8, 'sources': [{'url': 'https://example.org/job'}],
                 'claims': [{'path': '/location', 'confidence': .6}]}
        events = []
        with patch.object(client, 'request', side_effect=[
            {'id': 'run', 'web_search_agent_id': 'agent', 'status': 'queued'},
            {'status': 'running'}, {'status': 'completed'},
            {'output': {'type': 'json', 'content': {'title': 'Python Developer'}, 'trust': trust}},
        ]) as request, patch.object(adapter, 'progress'), patch('adapters.nimble.agent.time.sleep'):
            result = adapter.structured('Check supplied opening', {'type': 'object'}, 'match', events.append)
        creation = request.call_args_list[0]
        self.assertEqual(creation.args[2]['use_case'], 'research')
        self.assertEqual(creation.kwargs['retries'], 0)
        self.assertTrue(creation.args[2]['enable_events'])
        self.assertEqual([call.args[1] for call in request.call_args_list[1:]],
                         ['agents/agent/runs/run', 'agents/agent/runs/run', 'agents/agent/runs/run/result'])
        self.assertEqual(result.content['title'], 'Python Developer')
        self.assertEqual(result.trust, trust)
        self.assertEqual((result.run_id, result.agent_id), ('run', 'agent'))
        self.assertEqual([e['data']['status'] for e in events if e['type'] == 'provider_status'],
                         ['queued', 'running', 'completed'])

    def test_remote_timeout_reports_ids_without_resubmitting(self):
        client = self.client(agent_timeout=0); adapter = NimbleAgent(client)
        with patch.object(client, 'request', return_value={'id': 'r', 'web_search_agent_id': 'a', 'status': 'running'}) as request, \
             patch.object(adapter, 'progress'), self.assertRaisesRegex(ProviderError, 'remote task may continue.*Run: r; agent: a'):
            adapter.structured('Task', {}, 'match', lambda e: None)
        self.assertEqual(request.call_count, 1)

    def test_progress_forwards_only_public_messages(self):
        class Stream:
            status_code = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def iter_lines(self):
                return iter([': heartbeat', 'data: invalid', 'data: []',
                             'data: {"type":"private","message":"hidden"}',
                             'data: {"type":"progress","message":"Reading employer page"}',
                             'data: {"type":"progress","message":"Reading employer page"}'])
        events = []
        with patch('adapters.nimble.agent.httpx.Client') as http:
            http.return_value.__enter__.return_value.stream.return_value = Stream()
            NimbleAgent(self.client()).progress('agents/a/runs/r', 'match', events.append, threading.Event())
        self.assertEqual([e['message'] for e in events], ['Reading employer page'])

    def test_validation_error_does_not_echo_request_data(self):
        with patch('adapters.nimble.client.httpx.Client') as http:
            http.return_value.__enter__.return_value.request.return_value = httpx.Response(
                422, json={'detail': [{'msg': 'String too long', 'input': 'PRIVATE RESUME'}]})
            with self.assertRaises(ProviderError) as error:
                self.client().request('POST', 'agents/runs', {'input': 'PRIVATE RESUME'}, retries=0)
        self.assertIn('String too long', str(error.exception))
        self.assertNotIn('PRIVATE RESUME', str(error.exception))

    def test_composition_uses_distinct_adapters_and_shared_transport(self):
        services = build_services(Settings(api_key='fixture-key'))
        self.assertIsInstance(services.search, NimbleSearch)
        self.assertIsInstance(services.extract, NimbleExtract)
        self.assertIsInstance(services.reasoner, NimbleAgent)
        self.assertIs(services.search.client, services.extract.client)
        self.assertIs(services.extract.client, services.reasoner.client)
