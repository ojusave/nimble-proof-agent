import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from proof.agent import Agent, canonical_url, markdown
from proof.demo import DemoWeb, DemoModel, QUESTION
from proof.providers import Nimble, ProviderError
from proof.server import make_server
from proof.storage import Store


class AgentTests(unittest.TestCase):
    def prepared(self):
        agent = Agent(DemoWeb(), DemoModel())
        agent.search('Atlas versus Beacon')
        return agent

    def brief(self, quote='Scheduled CSV exports run every day.'):
        return {'title':'Comparison', 'summary':'Atlas exports daily.', 'findings':[
            {'claim':'Atlas exports daily.', 'source_id':'S1', 'quote':quote}], 'gaps':['Only one source checked.']}

    def test_full_agent_loop(self):
        result = Agent(DemoWeb(), DemoModel()).run(QUESTION)
        self.assertEqual(result['tool_calls'], 4)
        self.assertEqual(len(result['brief']['findings']), 4)
        self.assertTrue(all(source['read'] for source in result['sources']))
        self.assertIn('https://atlas.example.com', markdown(result))

    def test_rejects_unread_evidence(self):
        with self.assertRaisesRegex(ValueError, 'successfully read'):
            self.prepared().finish(self.brief())

    def test_rejects_fabricated_quotes(self):
        agent = self.prepared(); agent.read('S1')
        with self.assertRaisesRegex(ValueError, 'not found'):
            agent.finish(self.brief('Private networking is free for everyone.'))

    def test_accepts_whitespace_variation(self):
        agent = self.prepared(); agent.read('S1')
        self.assertEqual(agent.finish(self.brief('Scheduled CSV exports\nrun every day.'))['title'], 'Comparison')

    def test_deduplicates_sources(self):
        agent = self.prepared(); agent.search('Another query')
        self.assertEqual(len(agent.sources), 2)

    def test_unknown_source_cannot_be_fetched(self):
        with self.assertRaises(ValueError):
            self.prepared().read('https://malicious.example')

    def test_tool_budget_is_enforced(self):
        with self.assertRaisesRegex(ProviderError, 'budget'):
            Agent(DemoWeb(), DemoModel(), max_calls=1).run(QUESTION)

    def test_recovers_after_bad_quote(self):
        class Recovering(DemoModel):
            def next(self, *args, **kwargs):
                blocks = super().next(*args, **kwargs)
                if self.turn == 3:
                    blocks[0]['input']['findings'][0]['quote'] = 'This quotation does not exist.'
                return blocks
        result = Agent(DemoWeb(), Recovering()).run(QUESTION)
        self.assertEqual(result['tool_calls'], 5)
        self.assertTrue(any(e['type'] == 'tool_error' for e in result['events']))

    def test_tool_failures_do_not_become_evidence(self):
        agent = self.prepared()
        with patch.object(agent.web, 'extract', side_effect=ProviderError('Unavailable')):
            with self.assertRaises(ProviderError): agent.read('S1')
        self.assertFalse(agent.sources['S1']['read'])

    def test_disallows_local_source_urls(self):
        for url in ['http://example.com', 'https://localhost/x', 'https://127.0.0.1/', 'https://10.0.0.1/', 'https://[::1]/', 'https://user:pass@example.com/', 'https://example.com:8000/']:
            with self.subTest(url=url), self.assertRaises(ValueError): canonical_url(url)

    def test_nimble_request_contract(self):
        with patch.dict('os.environ', {'NIMBLE_API_KEY':'fixture-key'}), patch('proof.providers.post_json') as post:
            post.return_value = {'results':[{'url':'https://example.com/'}]}
            self.assertEqual(len(Nimble().search('query')), 1)
            self.assertEqual(post.call_args.args[0], 'https://sdk.nimbleway.com/v2/search')
            self.assertEqual(post.call_args.args[1]['max_results'], 5)
            post.return_value = {'status':'success','data':{'markdown':'Evidence text'}}
            self.assertEqual(Nimble().extract('https://example.com/'), 'Evidence text')
            self.assertEqual(post.call_args.args[0], 'https://sdk.nimbleway.com/v2/extract')

    def test_failed_extract_is_rejected(self):
        with patch.dict('os.environ', {'NIMBLE_API_KEY':'fixture-key'}), patch('proof.providers.post_json', return_value={'status':'blocked'}):
            with self.assertRaises(ProviderError): Nimble().extract('https://example.com/')


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = make_server(0, Path(self.temp.name) / 'test.db')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:%s' % self.server.server_port

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temp.cleanup()

    def request(self, path, body=None, headers=None):
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type':'application/json', **(headers or {})})
        return urlopen(request, timeout=5)

    def test_job_to_persisted_export(self):
        import time
        with self.request('/api/runs', {'mode':'demo'}) as response:
            rid = json.load(response)['id']
        for _ in range(30):
            with self.request('/api/runs/' + rid) as response: run = json.load(response)
            if run['status'] != 'running': break
            time.sleep(.02)
        self.assertEqual(run['status'], 'complete')
        self.assertEqual(len(run['result']['brief']['findings']), 4)
        with self.request('/api/runs/' + rid + '/markdown') as response:
            self.assertIn('synthetic offline demo', response.read().decode())
        store = Store(Path(self.temp.name) / 'test.db')
        self.assertEqual(store.get(rid)['status'], 'complete')

    def test_blocks_foreign_origin(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/runs', {'mode':'demo'}, {'Origin':'https://foreign.example'})
        self.assertEqual(error.exception.code, 403)

    def test_no_dotenv_or_source_exposure(self):
        for path in ['/.env', '/proof/providers.py', '/../.env']:
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.request(path)
            self.assertEqual(error.exception.code, 404)

    def test_invalid_payload(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/runs', {'mode':'anything'})
        self.assertEqual(error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
