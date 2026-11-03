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
from core.models import SearchRequest,event
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
        self.assertEqual([r['text'] for r in result['requirements']],['Developer advocate','remote','US'])
        self.assertIsNotNone(result['next_question'])
        self.assertEqual(len([e for e in events if e['type']=='job_matched']),4)
        self.assertTrue(all(not j['provisional'] for j in result['jobs']))

    def test_planning_is_local_and_preserves_requirements_across_rounds(self):
        class NoRemotePlanning(DemoAdapter):
            def structured(self,*args,**kwargs):
                assert args[2]=='match', 'Planning must not create a paid research run'
                return super().structured(*args,**kwargs)
        result,events=self.run_workflow(NoRemotePlanning())
        self.assertEqual(len(result['jobs']),4)
        plans=[e['data'] for e in events if e['type']=='plan_ready']
        self.assertEqual(plans[0]['requirements'],plans[1]['requirements'])
        self.assertNotEqual(plans[0]['queries'],plans[1]['queries'])
        self.assertEqual(plans[0]['tool'],'Local planner')

    def test_stops_when_count_satisfied(self):
        result,_=self.run_workflow(count=1)
        self.assertEqual(len(result['jobs']),1)
        self.assertEqual(result['rounds'],1)

    def test_application_link_is_retained_in_results_and_live_events(self):
        class ApplicationPage(DemoAdapter):
            def extract(self,url):
                return super().extract(url)+' [Apply now]('+url+'/apply?source=listing#application)'
        result,events=self.run_workflow(ApplicationPage(),count=1)
        job=result['jobs'][0]
        self.assertEqual(job['application_url'],job['url']+'/apply?source=listing#application')
        self.assertEqual(job['application_link_source'],'listing_link')
        matched=next(e['data']['job'] for e in events if e['type']=='job_matched' and e['data']['job']['id']==job['id'])
        self.assertEqual(matched['application_url'],job['application_url'])

    def test_model_cannot_invent_resume_evidence(self):
        class Fabricator(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                value.content['strengths'][0]['resume_quote']='A skill never present in this résumé'
                return value
        result,_=self.run_workflow(Fabricator())
        self.assertEqual(result['jobs'],[])
        self.assertTrue(any('evidence' in r['reason'] for r in result['excluded']))

    def test_missing_resume_quotes_use_only_exact_shared_skill_evidence(self):
        class MissingQuote(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                for strength in value.content.get('strengths',[]): strength['resume_quote']=None
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
                value.content['checks']={'R1':{'status':'met','evidence':'A fabricated location'}}
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

    def test_malformed_assessment_does_not_abort_other_candidates(self):
        class Malformed(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                if value.content['company']=='Northstar Data':value.content['strengths']=123
                return value
        result,_=self.run_workflow(Malformed())
        self.assertEqual(len(result['jobs']),3)
        self.assertTrue(any(r['reason']=='Invalid assessment field: strengths' for r in result['excluded']))

    def test_requirement_keys_cannot_be_overridden_by_model_ids(self):
        class WrongIDs(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                for check in value.content['checks'].values():check['id']='R3'
                return value
        result,_=self.run_workflow(WrongIDs())
        self.assertEqual(len(result['jobs']),4)
        self.assertEqual([c['id'] for c in result['jobs'][0]['checks']],['R1','R2','R3'])

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

    def test_provider_updates_keep_their_round_and_candidate_identity(self):
        class ReportingAdapter(DemoAdapter):
            def structured(self,task,schema,purpose,emit):
                emit(event('provider_status',purpose,'Running',status='running'))
                return super().structured(task,schema,purpose,emit)
        _,events=self.run_workflow(ReportingAdapter())
        updates=[item for item in events if item['type']=='provider_status' and item['step']=='match']
        self.assertEqual(len(updates),6)
        self.assertTrue(all(len(item['data']['candidate_ids'])==1 for item in updates))
        self.assertTrue(all(item['data']['round']==1 for item in updates))
        self.assertEqual(len({item['data']['candidate_ids'][0] for item in updates}),6)

    def test_logs_do_not_include_resume_text(self):
        _,events=self.run_workflow()
        self.assertNotIn('Jordan Example',json.dumps(events))
        # Only selected, evidence-backed résumé quotations are published in result cards.
        self.assertNotIn('Eight years',json.dumps(events))

    def test_provider_trust_is_retained_without_overriding_missing_evidence(self):
        class ConfidentProvider(DemoAdapter):
            def structured(self,*args,**kwargs):
                value=super().structured(*args,**kwargs)
                value.content['checks']={'R1':{'status':'met','evidence':'Invented requirement evidence'}}
                value.trust={'confidence':0.99,'sources':[{'url':'https://example.org/policy'}]}
                value.run_id='fixture-run';value.agent_id='fixture-agent'
                return value
        result,events=self.run_workflow(ConfidentProvider())
        self.assertEqual(result['jobs'],[])
        self.assertTrue(result['unknowns'])
        job=result['unknowns'][0]
        self.assertEqual(job['research']['trust']['confidence'],0.99)
        self.assertEqual(job['research']['run_id'],'fixture-run')
        self.assertEqual(job['checks'][0]['status'],'unknown')
        self.assertTrue(job['evidence']['passages'])
        self.assertTrue(any(e['type']=='research_completed' for e in events))
        from core.exporting import shortlist_markdown
        exported=shortlist_markdown(result)
        self.assertIn('Needs review',exported)
        self.assertIn('fixture-run',exported)
        self.assertIn('https://example.org/policy',exported)


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
        self.assertIn('Résumé quote:',exported.text)
        self.assertIn('Needs review',exported.text)
        self.assertEqual(self.client.delete('/api/resumes/'+rid).status_code,200)
        self.assertEqual(self.client.get('/api/resumes').json(),[])
        self.assertEqual(list((self.root/'resumes').iterdir()),[])

    def test_repeated_sample_reuses_resume_and_preserves_source_evidence(self):
        first=self.client.post('/api/demo').json()['id']
        self.wait_for(first)
        second=self.client.post('/api/demo').json()['id']
        run=self.wait_for(second)
        self.assertEqual(len(self.repo.list_resumes()),1)
        jobs=run['result']['jobs']
        self.assertEqual(len({job['title'] for job in jobs}),len(jobs))
        self.assertTrue(all(job['strengths'][0]['job_quote'] in job['sample_listing'] for job in jobs))
        self.assertEqual(len(run['result']['unknowns']),1)

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


class StartupTests(unittest.TestCase):
    def test_busy_port_is_rejected_before_opening_storage(self):
        import socket
        import contextlib
        from unittest.mock import patch
        from app import main
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0))
            listener.listen()
            port=listener.getsockname()[1]
            with patch('sys.argv',['app.py','serve','--port',str(port)]), patch('api.app.create_app') as factory:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                    main()
                self.assertEqual(stopped.exception.code,2)
                factory.assert_not_called()
