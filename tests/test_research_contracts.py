"""Known-answer cases for the boundary between research and a recommendation.

These fixtures test acceptance rules, not live-web research accuracy.
Run: python -m unittest discover -s tests -p test_research_contracts.py -v
"""
import unittest
from copy import deepcopy
from adapters.demo import DemoAdapter, SAMPLE_RESUME
from core.settings import Settings
from workflows.job_matcher import JobWorkflow
from workflows.prompts import assessment_task
from workflows.schemas import assessment_schema


class ResearchContractTests(unittest.TestCase):
    def setUp(self):
        adapter=DemoAdapter()
        self.workflow=JobWorkflow(adapter,adapter,adapter,Settings(),lambda item:None)
        self.item={'id':'known-role','title':'Python Developer Advocate',
                   'url':'https://jobs.example.org/careers/1'}
        self.item['text']=adapter.extract(self.item['url'])
        self.state={'profile':SAMPLE_RESUME,'query':'remote, US',
                    'plan':{'requirements':[{'id':'R1','text':'remote, US'}]}}
        task,_,_=assessment_task(SAMPLE_RESUME,self.state['query'],self.state['plan']['requirements'],self.item)
        self.assessment=adapter.structured(task,assessment_schema(self.state['plan']['requirements']),
                                           'match',lambda item:None).content

    def decide(self,**changes):
        assessment={**deepcopy(self.assessment),**changes}
        assessment['checks']=[{**check,'id':key} for key,check in assessment['checks'].items()]
        return self.workflow.validate(self.item,assessment,self.state)

    def test_supported_role_and_requirements_can_be_a_match(self):
        verdict,job=self.decide()
        self.assertEqual(verdict,'match')
        self.assertTrue(job['strengths'])
        self.assertEqual(job['checks'][0]['status'],'met')

    def test_missing_or_fabricated_requirement_evidence_needs_review(self):
        for evidence in ('','Work remotely from any country.'):
            with self.subTest(evidence=evidence):
                verdict,job=self.decide(checks={'R1':{'status':'met','evidence':evidence}})
                self.assertEqual(verdict,'unknown')
                self.assertEqual(job['checks'][0]['status'],'unknown')

    def test_explicit_source_backed_conflict_is_excluded(self):
        self.item['text']+=' This role is onsite in London.'
        verdict,reason=self.decide(checks={'R1':{'status':'conflict','evidence':'This role is onsite in London.'}})
        self.assertEqual(verdict,'exclude')
        self.assertIn('Conflicts with',reason)

    def test_absent_or_malformed_assessment_is_unverified(self):
        for changes in ({'is_specific_opening':None},{'strengths':123},
                        {'employer_url':None},{'relevance':None},{'title':None},
                        {'strengths':[{'reason':'Unsupported','resume_quote':'Invented expertise',
                                       'job_quote':'Build Python integrations and teach developers.'}]}):
            with self.subTest(changes=changes): self.assertEqual(self.decide(**changes)[0],'unverified')
        self.assertEqual(self.workflow.validate(self.item,None,self.state)[0],'unverified')

    def test_unsubstantiated_closed_claim_does_not_reject_a_role(self):
        verdict,job=self.decide(open_status='closed',open_evidence='This job has been filled.')
        self.assertEqual(verdict,'unknown')
        self.assertIn('Current application availability',job['unknown_requirements'])

    def test_source_backed_closed_role_is_excluded(self):
        self.item['text']+=' This job has been filled.'
        self.assertEqual(self.decide(open_status='closed',open_evidence='This job has been filled.')[0],'exclude')

    def test_directory_is_not_a_specific_opening(self):
        self.assertEqual(self.decide(is_specific_opening=False)[0],'exclude')
