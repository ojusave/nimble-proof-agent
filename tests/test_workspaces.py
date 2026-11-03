"""Public access must never expose another browser's uploads, runs, or traces."""
import tempfile
import sqlite3
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from adapters.demo import DemoAdapter, SAMPLE_RESUME
from adapters.storage.sqlite import Repository
from api.app import create_app
from core.settings import Settings


class BrowserWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.repo=Repository(Path(self.temp.name))
        self.legacy=self.repo.save_resume('older-upload.txt',SAMPLE_RESUME.encode(),SAMPLE_RESUME)
        self.app=create_app(Settings(data_dir=Path(self.temp.name)),self.repo,DemoAdapter())
        self.a=TestClient(self.app,headers={'x-proof-workspace':'a'*64})
        self.b=TestClient(self.app,headers={'x-proof-workspace':'b'*64})

    def tearDown(self):
        self.a.close();self.b.close();self.temp.cleanup()

    def completed_sample(self):
        response=self.a.post('/api/demo')
        self.assertEqual(response.status_code,202)
        rid=response.json()['id']
        for _ in range(200):
            run=self.a.get('/api/searches/'+rid).json()
            if run['status']!='running': return run
            time.sleep(.02)
        self.fail('Sample did not complete')

    def test_legacy_uploads_stay_local_and_new_visitors_start_empty(self):
        self.assertIsNotNone(self.repo.resume(self.legacy['id']))
        for client in (self.a,self.b):
            self.assertEqual(client.get('/api/resumes').json(),[])
            self.assertEqual(client.get('/api/searches').json(),[])
            self.assertEqual(client.delete('/api/resumes/'+self.legacy['id']).status_code,404)
        self.assertEqual(self.a.get('/api/resumes',headers={'x-proof-workspace':'local'}).status_code,400)

    def test_existing_database_migrates_without_moving_or_deleting_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with sqlite3.connect(root/'jobs.db') as db:
                db.execute('CREATE TABLE resumes(id TEXT PRIMARY KEY,name TEXT,text TEXT,created TEXT,path TEXT)')
                db.execute('INSERT INTO resumes VALUES(?,?,?,?,?)',('old-id','old.txt','Private older resume','2026-01-01',''))
            migrated=Repository(root)
            self.assertEqual(migrated.resume('old-id')['text'],'Private older resume')
            self.assertEqual(migrated.scoped('a'*64).list_resumes(),[])
            self.assertIsNone(migrated.scoped('a'*64).resume('old-id'))

    def test_every_saved_run_surface_is_scoped_to_its_browser(self):
        run=self.completed_sample();rid=run['id'];prefix='/api/searches/'+rid
        self.assertEqual(self.b.get('/api/resumes').json(),[])
        self.assertEqual(self.b.get('/api/searches').json(),[])
        for path in ('','/events','/trace','/export'):
            with self.subTest(path=path): self.assertEqual(self.b.get(prefix+path).status_code,404)
        for path,body in [('/stop',{}),('/tailor',{'job_id':'some-role'}),
                          ('/resume-draft',{'job_id':'some-role','edits':[0]})]:
            with self.subTest(path=path): self.assertEqual(self.b.post(prefix+path,json=body).status_code,404)
        self.assertEqual(self.b.post('/api/agent',json={'threadId':'test','runId':'test',
            'forwardedProps':{'search_id':rid}}).status_code,404)
        self.assertEqual(self.b.post('/api/searches',json={'resume_id':run['resume_id'],'demo':True}).status_code,400)
        self.assertEqual(self.b.delete('/api/resumes/'+run['resume_id']).status_code,404)
        other=self.repo.scoped('b'*64)
        other.finish(rid,error='foreign write');other.emit(rid,{'type':'foreign-event'});other.request_stop(rid)
        self.assertEqual(other.events(rid),[])
        self.assertEqual(self.a.get(prefix).json()['status'],'complete')
        self.assertEqual(self.a.get(prefix+'/trace').status_code,200)

    def test_deleting_resume_keeps_own_history_without_exposing_it_to_others(self):
        run=self.completed_sample()
        self.assertEqual(self.a.delete('/api/resumes/'+run['resume_id']).status_code,200)
        self.assertEqual(self.a.get('/api/resumes').json(),[])
        self.assertEqual(len(self.a.get('/api/searches').json()),1)
        self.assertEqual(self.a.get('/api/searches/'+run['id']).status_code,200)
        self.assertEqual(self.b.get('/api/searches').json(),[])
