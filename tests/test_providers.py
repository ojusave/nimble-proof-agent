import unittest
from unittest.mock import patch
import httpx
from core.settings import Settings
from adapters.nimble.client import NimbleAdapter,ProviderError


class ProviderTests(unittest.TestCase):
    def adapter(self):return NimbleAdapter(Settings(api_key='fixture-key',agent_timeout=0))

    def test_research_uses_events_and_avoids_creation_retry(self):
        adapter=self.adapter();calls=[]
        def request(method,path,payload=None,retries=1):
            calls.append((method,path,payload,retries))
            if method=='POST':return {'id':'r','web_search_agent_id':'a','status':'completed'}
            return {'output':{'type':'json','content':{'jobs':[{'candidate_id':'J1'}]}}}
        with patch.object(adapter,'request',side_effect=request),patch.object(adapter,'progress'):
            result=adapter.structured('Evaluate supplied data',{'type':'object'},'match',lambda e:None)
        self.assertEqual(calls[0][2]['use_case'],'research')
        self.assertEqual(calls[0][3],0)
        self.assertTrue(calls[0][2]['enable_events'])
        self.assertEqual(result['jobs'][0]['candidate_id'],'J1')

    def test_remote_timeout_reports_ids_without_resubmitting(self):
        adapter=self.adapter()
        with patch.object(adapter,'request',return_value={'id':'r','web_search_agent_id':'a','status':'running'}) as request, \
             patch.object(adapter,'progress'), self.assertRaisesRegex(ProviderError,'remote task may continue'):
            adapter.structured('Task',{},'plan',lambda e:None)
        self.assertEqual(request.call_count,1)

    def test_validation_error_does_not_echo_request_data(self):
        class Client:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def request(self,*args,**kwargs):
                return httpx.Response(422,json={'detail':[{'msg':'String too long','input':'PRIVATE RESUME'}]})
        with patch('adapters.nimble.client.httpx.Client',return_value=Client()),self.assertRaises(ProviderError) as error:
            self.adapter().request('POST','agents/runs',{'input':'PRIVATE RESUME'},retries=0)
        self.assertIn('String too long',str(error.exception))
        self.assertNotIn('PRIVATE RESUME',str(error.exception))
