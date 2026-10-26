import unittest
from unittest.mock import patch
from proof.hosted import NimbleAgent
from proof.providers import ProviderError


class HostedTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict('os.environ', {'NIMBLE_API_KEY':'fixture-key'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.content = {'title':'A short brief', 'summary':'A feature.', 'findings':[
            {'claim':'Daily exports are supported.', 'source_url':'https://example.com/docs',
             'quote':'Scheduled CSV exports run every day.'}], 'gaps':['One source only.']}
        self.output = {'output':{'type':'json','content':self.content,'trust':{
            'sources':[{'url':'https://example.com/docs'}], 'claims':[], 'confidence':'high'}}}

    def test_hosted_lifecycle_and_independent_quote_check(self):
        with patch('proof.hosted.post_json', return_value={'id':'run-1','web_search_agent_id':'agent-1','status':'queued'}) as post, \
             patch('proof.hosted.get_json', side_effect=[{'status':'completed'}, self.output]) as get, \
             patch('proof.hosted.Nimble.extract', return_value='Scheduled CSV exports run every day.'):
            result = NimbleAgent(poll_interval=0).run('Does it support exports?')
        self.assertEqual(result['provider'], 'Nimble Agent API')
        self.assertTrue(result['sources'][0]['read'])
        self.assertEqual(post.call_args.kwargs['retries'], 0)
        self.assertEqual(post.call_args.args[1]['effort'], 'low')
        self.assertTrue(get.call_args.args[0].endswith('/agents/agent-1/runs/run-1/result'))

    def test_rejects_invented_source(self):
        self.output['output']['trust']['sources'] = [{'url':'https://unrelated.example.com/'}]
        with self.assertRaisesRegex(ProviderError, 'absent'):
            NimbleAgent().check_result('question', self.output, 'a', 'r')

    def test_rejects_quote_missing_from_fresh_extract(self):
        with patch('proof.hosted.Nimble.extract', return_value='A different page entirely.'), \
             self.assertRaisesRegex(ProviderError, 'No findings'):
            NimbleAgent().check_result('question', self.output, 'a', 'r')

    def test_failed_remote_run(self):
        with patch('proof.hosted.post_json', return_value={'id':'r','web_search_agent_id':'a','status':'failed'}), \
             self.assertRaisesRegex(ProviderError, 'failed'):
            NimbleAgent().run('A research question')

    def test_timeout_does_not_resubmit(self):
        with patch('proof.hosted.post_json', return_value={'id':'r','web_search_agent_id':'a','status':'running'}) as post, \
             self.assertRaisesRegex(ProviderError, 'may continue'):
            NimbleAgent(timeout=0).run('A research question')
        self.assertEqual(post.call_count, 1)

    def test_sources_report_without_confidence_grades(self):
        output = self.output['output']
        output['sources'] = output['trust']['sources']
        output['trust'] = None
        self.content['findings'].append({'claim':'Missing detail', 'quote':None, 'source_url':None})
        with patch('proof.hosted.Nimble.extract', return_value='Scheduled CSV exports run every day.'):
            result = NimbleAgent().check_result('question', self.output, 'a', 'r')
        self.assertEqual(len(result['brief']['findings']), 1)
        self.assertTrue(any('Missing detail' in gap for gap in result['brief']['gaps']))
        self.assertTrue(any('confidence grades' in gap for gap in result['brief']['gaps']))

    def test_partial_result_lists_rejected_quote_as_gap(self):
        self.content['findings'].append({'claim':'Unsupported claim', 'quote':'This quotation does not exist.', 'source_url':'https://example.com/docs'})
        with patch('proof.hosted.Nimble.extract', return_value='Scheduled CSV exports run every day.'):
            result = NimbleAgent().check_result('question', self.output, 'a', 'r')
        self.assertEqual(len(result['brief']['findings']), 1)
        self.assertTrue(any('Excluded finding' in gap for gap in result['brief']['gaps']))
        self.assertIn('passed quote checks', result['brief']['summary'])
