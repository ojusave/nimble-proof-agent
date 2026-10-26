import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from adapters.demo import DemoAdapter,SAMPLE_RESUME
from adapters.resume.parser import parse_resume,professional_text
from adapters.storage.sqlite import Repository
from core.settings import Settings
from core.models import SearchRequest
from workflows.job_matcher import JobWorkflow,contains
from runners.langgraph import LangGraphRunner
from api.app import create_app


class WorkflowTests(unittest.TestCase):
    def run_workflow(self,provider=None,count=5,rounds=2):
        adapter=provider or DemoAdapter();events=[]
        workflow=JobWorkflow(adapter,adapter,adapter,Settings(),events.append)
        result=LangGraphRunner().run(workflow,{'resume_text':SAMPLE_RESUME,'query':'Developer advocate, remote, US',
               'count':count,'max_rounds':rounds,'demo':True})
        return result,events

    def test_evidence_accepts_typographic_quotes_but_not_changed_words(self):
        self.assertTrue(contains("We're hiring Python developers",'We’re hiring Python developers.'))
        self.assertFalse(contains("We're hiring Java developers",'We’re hiring Python developers.'))

    def test_graph_strict_filters_and_shortfall(self):
        result,events=self.run_workflow()
        self.assertEqual(len(result['jobs']),4)
        self.assertEqual(len(result['unknowns']),1)
        self.assertEqual(result['shortfall'],1)
        self.assertEqual(result['rounds'],2)
        self.assertTrue(any('Conflicts' in r['reason'] for r in result['excluded']))
        self.assertEqual(result['requirements'][0]['text'],'Remote within the United States')
        self.assertIsNotNone(result['next_question'])
        self.assertEqual(len([e for e in events if e['type']=='job_matched']),4)
        self.assertTrue(all(not j['provisional'] for j in result['jobs']))

    def test_original_query_survives_empty_planner_requirements(self):
        class EmptyPlan(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                if args[2]=='plan':value['requirements']=[]
                return value
        result,_=self.run_workflow(EmptyPlan())
        self.assertEqual(len(result['jobs']),4)
        self.assertTrue(any(r['text']=='remote' for r in result['requirements']))
        self.assertTrue(any(r['text']=='US' for r in result['requirements']))

    def test_stops_when_count_satisfied(self):
        result,_=self.run_workflow(count=1)
        self.assertEqual(len(result['jobs']),1)
        self.assertEqual(result['rounds'],1)

    def test_model_cannot_invent_resume_evidence(self):
        class Fabricator(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                if 'strengths' in value:value['strengths'][0]['resume_quote']='A skill never present in this résumé'
                return value
        result,_=self.run_workflow(Fabricator())
        self.assertEqual(result['jobs'],[])
        self.assertTrue(any('evidence' in r['reason'] for r in result['excluded']))

    def test_missing_resume_quotes_use_only_exact_shared_skill_evidence(self):
        class MissingQuote(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                for strength in value.get('strengths',[]): strength['resume_quote']=None
                return value
        result,_=self.run_workflow(MissingQuote())
        self.assertTrue(result['jobs'])
        for job in result['jobs']:
            for strength in job['strengths']:
                self.assertIn(strength['resume_quote'],SAMPLE_RESUME)
                self.assertTrue(strength['reason'].startswith('Shared skill:'))

    def test_missing_requirement_evidence_is_unknown(self):
        class MissingEvidence(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                if 'checks' in value:value['checks']={'R1':{'status':'met','evidence':'A fabricated location'}}
                return value
        result,_=self.run_workflow(MissingEvidence())
        self.assertEqual(result['jobs'],[])
        self.assertGreater(len(result['unknowns']),0)

    def test_source_failure_does_not_abort_all_candidates(self):
        class BrokenPage(DemoAdapter):
            def extract(self,url):
                if url.endswith('/1'): raise ValueError('Source unavailable')
                return super().extract(url)
        result,_=self.run_workflow(BrokenPage())
        self.assertEqual(len(result['jobs']),3)

    def test_long_documents_fit_hosted_input_limit(self):
        class BudgetRecorder(DemoAdapter):
            def __init__(self): self.sizes=[]
            def extract(self,url): return super().extract(url)+' extra listing content'*2000
            def structured(self,task,*args,**kwargs):
                self.sizes.append(len(task))
                return super().structured(task,*args,**kwargs)
        adapter=BudgetRecorder()
        workflow=JobWorkflow(adapter,adapter,adapter,Settings(),lambda e:None)
        LangGraphRunner().run(workflow,{'resume_text':SAMPLE_RESUME+' more experience'*1000,
            'query':'Developer advocate, remote, US','count':1,'max_rounds':1,'demo':True})
        self.assertTrue(adapter.sizes)
        self.assertLessEqual(max(adapter.sizes),10000)

    def test_logs_do_not_include_resume_text(self):
        _,events=self.run_workflow()
        self.assertNotIn('Jordan Example',json.dumps(events))
        # Only selected, evidence-backed résumé quotations are published in result cards.
        self.assertNotIn('Eight years',json.dumps(events))


class ResumeTests(unittest.TestCase):
    def test_text_and_contacts(self):
        self.assertIn('Python',parse_resume('resume.txt',SAMPLE_RESUME.encode()))
        text=professional_text('Python developer email test@example.com phone +1 (555) 222-3333')
        self.assertNotIn('test@example.com',text)
        self.assertNotIn('222-3333',text)

    def test_docx(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+SAMPLE_RESUME+'</w:t></w:r></w:p></w:body></w:document>')
        self.assertIn('Python',parse_resume('resume.docx',stream.getvalue()))

    def test_pdf_and_scanned_pdf(self):
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(width=100,height=100)
        stream=io.BytesIO();writer.write(stream)
        with self.assertRaisesRegex(ValueError,'readable text'):
            parse_resume('resume.pdf',stream.getvalue())
        # A tiny valid text-based PDF exercises the actual extraction path.
        text=SAMPLE_RESUME.replace('\n',' ')
        content=('BT /F1 10 Tf 10 150 Td ('+text.replace('—','-')+') Tj ET').encode()
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        writer=PdfWriter();page=writer.add_blank_page(width=800,height=200)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream_obj=DecodedStreamObject();stream_obj.set_data(content);page[NameObject('/Contents')]=writer._add_object(stream_obj)
        buf=io.BytesIO();writer.write(buf)
        self.assertIn('Python',parse_resume('resume.pdf',buf.getvalue()))

    def test_bad_upload(self):
        for name,data in [('resume.exe',b'a'*100),('resume.txt',b'short'),('resume.pdf',b'not a pdf')]:
            with self.subTest(name=name),self.assertRaises(ValueError):parse_resume(name,data)


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.repo=Repository(self.root)
        self.app=create_app(Settings(data_dir=self.root),self.repo,DemoAdapter())
        self.client=TestClient(self.app)

    def tearDown(self):self.client.close();self.temp.cleanup()

    def wait_for(self,rid):
        for _ in range(100):
            value=self.client.get('/api/searches/'+rid).json()
            if value['status']!='running':return value
            time.sleep(.02)
        self.fail('Search failed to finish.')

    def test_upload_default_count_run_stream_and_export(self):
        response=self.client.post('/api/resumes',files={'file':('resume.txt',SAMPLE_RESUME.encode(),'text/plain')})
        self.assertEqual(response.status_code,201)
        rid=response.json()['id']
        started=self.client.post('/api/searches',json={'resume_id':rid,'query':'remote US'})
        self.assertEqual(started.status_code,202)
        search_id=started.json()['id'];run=self.wait_for(search_id)
        self.assertEqual(run['count'],5);self.assertEqual(run['result']['shortfall'],1)
        stream=self.client.get('/api/searches/'+search_id+'/events')
        self.assertIn('text/event-stream',stream.headers['content-type'])
        self.assertIn('event: activity',stream.text);self.assertIn('event: done',stream.text)
        self.assertIn('job_matched',stream.text)
        exported=self.client.get('/api/searches/'+search_id+'/export')
        self.assertIn('4 of 5',exported.text)
        self.assertEqual(self.client.delete('/api/resumes/'+rid).status_code,200)
        self.assertEqual(self.client.get('/api/resumes').json(),[])
        self.assertEqual(list((self.root/'resumes').iterdir()),[])

    def test_missing_resume_invalid_count_and_origin(self):
        self.assertEqual(self.client.post('/api/searches',json={'resume_id':'missing'}).status_code,400)
        self.assertEqual(self.client.post('/api/searches',json={'resume_id':'x','count':0}).status_code,422)
        self.assertEqual(self.client.post('/api/demo',headers={'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.get('/.env').status_code,404)

    def test_concurrent_event_writes_are_not_lost(self):
        from concurrent.futures import ThreadPoolExecutor
        resume=self.repo.save_resume('r.txt',SAMPLE_RESUME.encode(),SAMPLE_RESUME)
        rid=self.repo.create(SearchRequest(resume['id']))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i:self.repo.emit(rid,{'type':'test','number':i}),range(30)))
        self.assertEqual(len(self.repo.events(rid)),30)

    def test_sse_reconnect_replays_only_new_events(self):
        response=self.client.post('/api/demo');rid=response.json()['id'];self.wait_for(rid)
        events=self.repo.events(rid);cursor=events[-2]['seq']
        stream=self.client.get('/api/searches/'+rid+'/events',headers={'Last-Event-ID':str(cursor)})
        self.assertEqual(stream.text.count('event: activity'),1)
        self.assertIn('event: done',stream.text)
