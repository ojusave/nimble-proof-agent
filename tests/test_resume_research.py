import io,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import httpx
from pypdf import PdfWriter
from fastapi.testclient import TestClient
from adapters.llamaindex.parser import LlamaParsePDF
from adapters.resume.router import RoutedResumeParser
from adapters.demo import DemoAdapter,SAMPLE_RESUME
from adapters.storage.sqlite import Repository
from core.settings import Settings
from core.models import ResearchResult
from composition import ingest_resume
from runners.langgraph import LangGraphRunner
from workflows.job_matcher import JobWorkflow
from workflows.planning import plan_search
from workflows.resume_profile import resume_profile,resolve_location
from workflows.applicant_research import ApplicantResearch
from workflows.resume_tailoring import ResumeTailoring
from workflows.discovery import linked_openings
from api.app import create_app

class ResumeResearchTests(unittest.TestCase):
    def test_location_is_grounded_in_header_not_name_or_employment(self):
        self.assertIsNone(resume_profile('Jordan Example\nDeveloper Advocate\nExperience\nWorked in London')['location'])
        for location in ('San Francisco, CA','London, UK','Bengaluru, India','Berlin, Germany'):
            profile=resume_profile('Jordan Example\nLocation: '+location+'\nExperience\nWorked in Paris')
            self.assertEqual(profile['location']['text'],location)
            self.assertEqual(resolve_location(profile,'Remote')['text'],location)
            self.assertEqual(resolve_location(profile,'remote, New York, NY')['source'],'preferences')
            self.assertEqual(resolve_location(profile,'anywhere')['text'],'Anywhere')

    def test_location_only_preferences_keep_role_and_no_implicit_relaxation(self):
        loc={'text':'San Francisco, CA','source':'resume','evidence':'San Francisco, CA'}
        plan=plan_search('Software Engineer with Python','remote',1,location=loc)
        self.assertIn('"software engineer"',plan['queries'][0]);self.assertIn('San Francisco',plan['queries'][0])
        self.assertEqual(plan['requirements'][-1]['text'],'Work in or remotely from San Francisco, CA')
        second=plan_search('Software Engineer','remote',2,plan,loc)
        self.assertEqual(plan['requirements'],second['requirements'])
        self.assertNotEqual(plan['queries'],second['queries'])

    def test_llamaparse_upload_poll_and_pages_through_ingestion_graph(self):
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);buf=io.BytesIO();writer.write(buf)
        calls=[]
        def respond(request):
            calls.append(request)
            if request.method=='POST':
                self.assertIn(b'"tier": "agentic"',request.content)
                self.assertIn(b'"version": "2026-09-29"',request.content)
                return httpx.Response(200,json={'id':'parse-1'})
            return httpx.Response(200,json={'job':{'status':'COMPLETED'},'markdown':{'pages':[{'markdown':'# Jordan Example\nLocation: San Francisco, CA\n'+SAMPLE_RESUME}]}})
        settings=Settings(llama_api_key='test-only')
        parser=RoutedResumeParser(LlamaParsePDF(settings,httpx.MockTransport(respond)))
        parsed=ingest_resume(settings,'test.pdf',buf.getvalue(),parser)
        self.assertEqual(parsed['parser'],'llamaparse');self.assertEqual(parsed['parse_job_id'],'parse-1')
        self.assertEqual(parsed['profile']['location']['text'],'San Francisco, CA')
        self.assertEqual(len(calls),2);self.assertIn('expand=markdown',str(calls[1].url))
        self.assertEqual(ingest_resume(settings,'test.txt',SAMPLE_RESUME.encode(),parser)['parser'],'local')
        self.assertEqual(len(calls),2)

    def test_configured_cloud_failure_does_not_silently_fallback(self):
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);buf=io.BytesIO();writer.write(buf)
        parser=RoutedResumeParser(LlamaParsePDF(Settings(llama_api_key='SECRET'),httpx.MockTransport(lambda r:httpx.Response(401))))
        with self.assertRaisesRegex(ValueError,'access is unavailable') as error: parser.parse('test.pdf',buf.getvalue())
        self.assertNotIn('SECRET',str(error.exception))

    def test_storage_metadata_migrates_and_does_not_expose_full_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            import sqlite3
            db=sqlite3.connect(Path(directory)/'jobs.db');db.execute('CREATE TABLE resumes(id TEXT PRIMARY KEY,name TEXT,text TEXT,created TEXT,path TEXT)');db.commit();db.close()
            repo=Repository(directory)
            parsed=ingest_resume(Settings(),'sample.txt',('Location: London, UK\n'+SAMPLE_RESUME).encode())
            value=repo.save_resume('test.txt',b'data',parsed['text'],{k:v for k,v in parsed.items() if k!='text'})
            self.assertEqual(value['location']['text'],'London, UK');self.assertNotIn('pages',repo.list_resumes()[0])
            self.assertIn('metadata',repo.resume(value['id']))

    def test_captured_index_links_are_relevant_public_employer_urls(self):
        text='[Developer Advocate](https://jobs.ashbyhq.com/acme/01234567-aaaa-bbbb-cccc-123456789012) [Accountant](https://jobs.ashbyhq.com/acme/01234567-aaaa-bbbb-cccc-000000000001) [Developer](http://127.0.0.1/jobs/1)'
        links=linked_openings(text,'https://employer.example/careers',['developer advocate'])
        self.assertEqual(len(links),1);self.assertIn('123456789012',links[0]['url'])

    def test_parallel_nimble_branches_join_into_cited_reviewable_proposals(self):
        profile_started=threading.Event();search_started=threading.Event()
        class Provider(DemoAdapter):
            def search(self,*args):
                search_started.set()
                assert profile_started.wait(2),'Applicant research did not start concurrently'
                return super().search(*args)
            def extract(self,url):
                if url=='https://portfolio.example/project':return 'Jordan Example authored this project. Built Python integrations for public APIs.'
                return super().extract(url)
            def structured(self,task,schema,purpose,emit):
                if purpose=='profile':
                    profile_started.set();assert search_started.wait(2)
                    return ResearchResult(content={'facts':[{'claim':'Built a Python integration','source_url':'https://portfolio.example/project','source_quote':'Built Python integrations for public APIs.','identity_quote':'Jordan Example authored this project.','belongs_to_applicant':True}],'unresolved':[]},trust={},run_id='profile',agent_id='agent')
                if purpose=='tailor':
                    payload=json.loads(task[task.index('{'):]);quote=payload['job_passages'][0]['text'][:80]
                    return ResearchResult(content={'roles':[{'job_id':payload['job_id'],'edits':[{'wording':'Built Python integrations for public APIs.','evidence_id':'F1','job_quote':quote,'reason':'Relevant integration work.'},{'wording':'Invented','evidence_id':'FAKE','job_quote':quote,'reason':'No source'}],'remaining_gaps':['Production usage is not established.']}]},trust={},run_id='tailor',agent_id='agent')
                return super().structured(task,schema,purpose,emit)
        p=Provider();events=[]
        result=LangGraphRunner().run(JobWorkflow(p,p,p,Settings(candidates_per_round=1),events.append),{'resume_text':SAMPLE_RESUME,'query':'Developer advocate, remote, US','count':1,'max_rounds':1,'public_urls':['https://portfolio.example/project']})
        self.assertEqual(len(result['public_research']['facts']),1)
        job=result['jobs'][0];self.assertEqual(result['resume_proposals'],{})
        result['resume_proposals']=LangGraphRunner().run_tailoring(ResumeTailoring(p,p,events.append,lambda kind,step,message,**data: events.append({'type':kind,'step':step,'message':message,'data':data}),lambda:None),{'profile':SAMPLE_RESUME,'public_research':result['public_research'],'result':{'jobs':[job],'unknowns':[]}})
        self.assertEqual(len(result['resume_proposals'][job['id']]['edits']),1)
        kinds=[e['type'] for e in events]
        self.assertLess(kinds.index('candidate_discovered'),kinds.index('job_matched'))
        self.assertLess(kinds.index('job_matched'),kinds.index('resume_proposals_ready'))
        self.assertLess(kinds.index('search_completed'),kinds.index('resume_proposals_ready'))
        with tempfile.TemporaryDirectory() as directory:
            repo=Repository(directory);resume=repo.save_resume('resume.txt',SAMPLE_RESUME.encode(),SAMPLE_RESUME)
            from core.models import SearchRequest
            rid=repo.create(SearchRequest(resume['id']));repo.finish(rid,result)
            with TestClient(create_app(Settings(data_dir=Path(directory)),repository=repo)) as client:
                response=client.post('/api/searches/'+rid+'/resume-draft',json={'job_id':job['id'],'edits':[0]})
                self.assertEqual(response.status_code,200);self.assertIn('Selected professional work',response.json()['markdown'])
                self.assertEqual(repo.resume(resume['id'])['text'],SAMPLE_RESUME)
                self.assertEqual(client.post('/api/searches/'+rid+'/resume-draft',json={'job_id':job['id'],'edits':[-1]}).status_code,400)

    def test_unverifiable_external_quotes_do_not_become_resume_evidence(self):
        reasoner=Mock();reasoner.structured.return_value=ResearchResult(content={'facts':[{'claim':'False claim','source_url':'https://portfolio.example/work','source_quote':'Invented quotation','identity_quote':'Jordan Example','belongs_to_applicant':True}],'unresolved':[]},trust={},run_id='r',agent_id='a')
        extractor=Mock();extractor.extract.return_value='Jordan Example wrote something else.'
        worker=ApplicantResearch(reasoner,extractor,lambda e:None,lambda *a,**k:None,lambda:None)
        result=worker.research({'public_urls':['https://portfolio.example/work'],'query':'Engineer','profile':SAMPLE_RESUME})
        self.assertEqual(result['facts'],[])

    def test_upload_stream_contains_actual_ingestion_nodes_and_keeps_saved_provenance(self):
        with tempfile.TemporaryDirectory() as directory,TestClient(create_app(Settings(data_dir=Path(directory)))) as client:
            response=client.post('/api/resumes',headers={'Accept':'text/event-stream'},files={'file':('resume.txt',SAMPLE_RESUME.encode(),'text/plain')})
            self.assertEqual(response.status_code,200)
            packets=[]
            for packet in response.text.split('\n\n'):
                line=next((line[6:] for line in packet.splitlines() if line.startswith('data: ')),None)
                if line:packets.append(json.loads(line))
            nodes=[item for item in packets if item.get('type')=='node_started']
            self.assertEqual([node['data']['node'] for node in nodes],['parse','profile'])
            self.assertNotIn(SAMPLE_RESUME,response.text)
            resume=packets[-1];stored=client.app.state.repository.resume(resume['id'])
            self.assertEqual(len(json.loads(stored['metadata'])['ingestion_events']),4)
            bad=client.post('/api/resumes',headers={'Accept':'text/event-stream'},files={'file':('bad.txt',b'short','text/plain')})
            self.assertIn('event: error',bad.text)

    def test_actual_nested_node_spans_have_valid_parent_ids_and_outputs(self):
        provider=DemoAdapter();events=[]
        LangGraphRunner().run(JobWorkflow(provider,provider,provider,Settings(),events.append),{'resume_text':SAMPLE_RESUME,'query':'Developer advocate, remote, US','count':1,'max_rounds':1})
        starts={item['data']['span_id']:item for item in events if item['type']=='node_started'}
        ended={item['data']['span_id'] for item in events if item['type']=='node_completed'}
        self.assertEqual(set(starts),ended)
        for node in starts.values():
            if node['data']['graph']=='job-search': self.assertIn(node['data']['parent_id'],starts)
        self.assertNotIn(SAMPLE_RESUME,json.dumps(events))
