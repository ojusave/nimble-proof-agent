"""Local state and ordered events. Raw résumé text is never stored in events."""
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Repository:
    def __init__(self, root):
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
            ''')
            db.execute("UPDATE runs SET status='interrupted',error='Server restarted. Start a new search to continue.' WHERE status='running'")
        os.chmod(self.path,0o600)

    def connect(self):
        db=sqlite3.connect(self.path,timeout=20)
        db.row_factory=sqlite3.Row
        return db

    def save_resume(self,name,content,text):
        rid=uuid4().hex
        path=self.resumes/(rid+Path(name).suffix.lower())
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as out: out.write(content)
        created=datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('INSERT INTO resumes VALUES(?,?,?,?,?)',(rid,Path(name).name,text,created,str(path)))
        return {'id':rid,'name':Path(name).name,'created':created,'characters':len(text)}

    def list_resumes(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,name,created,length(text) AS characters FROM resumes ORDER BY created DESC')]

    def resume(self,rid):
        with self.connect() as db:
            row=db.execute('SELECT * FROM resumes WHERE id=?',(rid,)).fetchone()
        return dict(row) if row else None

    def delete_resume(self,rid):
        with self.connect() as db:
            row=db.execute('SELECT path FROM resumes WHERE id=?',(rid,)).fetchone()
            if row is None: return False
            if db.execute("SELECT 1 FROM runs WHERE resume_id=? AND status='running'",(rid,)).fetchone():
                raise ValueError('Wait for the active search before removing its résumé.')
            db.execute('DELETE FROM resumes WHERE id=?',(rid,))
        path=Path(row['path'])
        if path.parent.resolve()==self.resumes.resolve(): path.unlink(missing_ok=True)
        return True

    def create(self,request):
        rid=uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',(rid,datetime.now(timezone.utc).isoformat(),request.resume_id,request.query,request.count,'running',None,None))
        return rid

    def emit(self,rid,event):
        with self.connect() as db:
            db.execute('INSERT INTO events(run_id,payload) VALUES(?,?)',(rid,json.dumps(event)))
        with self.changed: self.changed.notify_all()

    def events(self,rid,after=0):
        with self.connect() as db:
            rows=db.execute('SELECT seq,payload FROM events WHERE run_id=? AND seq>? ORDER BY seq',(rid,after)).fetchall()
        return [{'seq':r['seq'],**json.loads(r['payload'])} for r in rows]

    def finish(self,rid,result=None,error=None):
        with self.connect() as db:
            db.execute('UPDATE runs SET status=?,result=?,error=? WHERE id=?',('failed' if error else 'complete',json.dumps(result) if result else None,error,rid))
        with self.changed: self.changed.notify_all()

    def run(self,rid):
        with self.connect() as db: row=db.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
        if row is None: return None
        result=dict(row);result['result']=json.loads(result['result']) if result['result'] else None
        return result

    def recent(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,created,query,count,status FROM runs ORDER BY created DESC LIMIT 20')]
