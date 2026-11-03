"""Local state and ordered events. Raw résumé text is never stored in events."""
import json
import os
import sqlite3
import threading
from copy import copy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Repository:
    def __init__(self, root):
        self.workspace = 'local'
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.resumes = self.root / 'resumes'
        self.resumes.mkdir(exist_ok=True)
        self.changed = threading.Condition()
        self.path = self.root / 'jobs.db'
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS resumes(id TEXT PRIMARY KEY,name TEXT,text TEXT,created TEXT,path TEXT);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,created TEXT,resume_id TEXT,query TEXT,count INTEGER,status TEXT,result TEXT,error TEXT);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,payload TEXT);
            CREATE INDEX IF NOT EXISTS events_run ON events(run_id,seq);
            CREATE TABLE IF NOT EXISTS workspace_resumes(resume_id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS workspace_owner ON workspace_resumes(workspace_id);
            ''')
            # Retain old uploads/history locally; never attach them to a new visitor.
            db.execute("INSERT OR IGNORE INTO workspace_resumes SELECT id,'local' FROM resumes")
            db.execute("INSERT OR IGNORE INTO workspace_resumes SELECT resume_id,'local' FROM runs")
            if 'metadata' not in {row['name'] for row in db.execute('PRAGMA table_info(resumes)')}:
                db.execute("ALTER TABLE resumes ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
            db.execute("UPDATE runs SET status='interrupted',error='Server restarted. Start a new search to continue.' WHERE status IN ('running','stopping')")
        os.chmod(self.path,0o600)

    def scoped(self, workspace):
        """A cheap request view; do not reopen/init storage or interrupt active runs."""
        view=copy(self)
        view.workspace=workspace
        return view

    def connect(self):
        db=sqlite3.connect(self.path,timeout=20)
        db.row_factory=sqlite3.Row
        return db

    def save_resume(self,name,content,text,metadata=None):
        rid=uuid4().hex
        path=self.resumes/(rid+Path(name).suffix.lower())
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as out: out.write(content)
        created=datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('INSERT INTO resumes(id,name,text,created,path,metadata) VALUES(?,?,?,?,?,?)',
                       (rid,Path(name).name,text,created,str(path),json.dumps(metadata or {})))
            db.execute('INSERT INTO workspace_resumes VALUES(?,?)',(rid,self.workspace))
        return self.resume_summary({'id':rid,'name':Path(name).name,'created':created,'characters':len(text),'metadata':json.dumps(metadata or {})})

    @staticmethod
    def resume_summary(row):
        result=dict(row);metadata=json.loads(result.pop('metadata') or '{}')
        return {**result,'location':metadata.get('profile',{}).get('location'),'parser':metadata.get('parser','local')}

    def list_resumes(self):
        with self.connect() as db:
            return [self.resume_summary(r) for r in db.execute('''SELECT id,name,created,length(text) AS characters,metadata
                FROM resumes JOIN workspace_resumes ON resume_id=id WHERE workspace_id=? ORDER BY created DESC''',(self.workspace,))]

    def resume(self,rid):
        with self.connect() as db:
            row=db.execute('''SELECT resumes.* FROM resumes JOIN workspace_resumes ON resume_id=id
                WHERE id=? AND workspace_id=?''',(rid,self.workspace)).fetchone()
        return dict(row) if row else None

    def delete_resume(self,rid):
        with self.connect() as db:
            row=db.execute('''SELECT path FROM resumes JOIN workspace_resumes ON resume_id=id
                WHERE id=? AND workspace_id=?''',(rid,self.workspace)).fetchone()
            if row is None: return False
            if db.execute("SELECT 1 FROM runs WHERE resume_id=? AND status IN ('running','stopping')",(rid,)).fetchone():
                raise ValueError('Wait for the active search before removing its résumé.')
            db.execute('DELETE FROM resumes WHERE id=?',(rid,))
        path=Path(row['path'])
        if path.parent.resolve()==self.resumes.resolve(): path.unlink(missing_ok=True)
        return True

    def create(self,request):
        if self.resume(request.resume_id) is None: raise ValueError('Résumé not found.')
        rid=uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',(rid,datetime.now(timezone.utc).isoformat(),request.resume_id,request.query,request.count,'running',None,None))
        return rid

    def emit(self,rid,event):
        with self.connect() as db:
            db.execute('''INSERT INTO events(run_id,payload) SELECT runs.id,? FROM runs
                JOIN workspace_resumes USING(resume_id) WHERE runs.id=? AND workspace_id=?''',
                (json.dumps(event),rid,self.workspace))
        with self.changed: self.changed.notify_all()

    def events(self,rid,after=0):
        with self.connect() as db:
            rows=db.execute('''SELECT seq,payload FROM events JOIN runs ON run_id=runs.id
                JOIN workspace_resumes USING(resume_id) WHERE run_id=? AND seq>? AND workspace_id=? ORDER BY seq''',
                (rid,after,self.workspace)).fetchall()
        return [{'seq':r['seq'],**json.loads(r['payload'])} for r in rows]

    def finish(self,rid,result=None,error=None,status=None):
        with self.connect() as db:
            db.execute('''UPDATE runs SET status=?,result=?,error=? WHERE id=? AND resume_id IN
                (SELECT resume_id FROM workspace_resumes WHERE workspace_id=?)''',
                (status or ('failed' if error else 'complete'),json.dumps(result) if result else None,error,rid,self.workspace))
        with self.changed: self.changed.notify_all()

    def request_stop(self,rid):
        with self.connect() as db:
            db.execute("""UPDATE runs SET status='stopping' WHERE id=? AND status='running' AND resume_id IN
                (SELECT resume_id FROM workspace_resumes WHERE workspace_id=?)""",(rid,self.workspace))

    def run(self,rid):
        with self.connect() as db:
            row=db.execute('''SELECT runs.* FROM runs JOIN workspace_resumes USING(resume_id)
                WHERE runs.id=? AND workspace_id=?''',(rid,self.workspace)).fetchone()
            if row is None: return None
            first=db.execute('SELECT payload FROM events WHERE run_id=? ORDER BY seq LIMIT 1',(rid,)).fetchone()
        result=dict(row);result['result']=json.loads(result['result']) if result['result'] else None
        result['public_urls']=json.loads(first['payload']).get('data',{}).get('public_urls',[]) if first else []
        return result

    def recent(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT id,created,query,count,status FROM runs
                JOIN workspace_resumes USING(resume_id) WHERE workspace_id=? ORDER BY created DESC LIMIT 20''',(self.workspace,))]
