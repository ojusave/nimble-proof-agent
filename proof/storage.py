"""One SQLite database per local installation; no account or cloud database needed."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT, question TEXT, mode TEXT, status TEXT, events TEXT, result TEXT, error TEXT)')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def create(self, question, mode):
        rid = uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)',
                       (rid, datetime.now(timezone.utc).isoformat(), question, mode, 'running', '[]', None, None))
        return rid

    def event(self, rid, event):
        with self.connect() as db:
            row = db.execute('SELECT events FROM runs WHERE id=?', (rid,)).fetchone()
            events = json.loads(row['events']) + [event]
            db.execute('UPDATE runs SET events=? WHERE id=?', (json.dumps(events), rid))

    def finish(self, rid, result=None, error=None):
        with self.connect() as db:
            db.execute('UPDATE runs SET status=?,result=?,error=? WHERE id=?',
                       ('failed' if error else 'complete', json.dumps(result) if result else None, error, rid))

    def get(self, rid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM runs WHERE id=?', (rid,)).fetchone()
        if row is None:
            return None
        value = dict(row)
        for key in ('events', 'result'):
            value[key] = json.loads(value[key]) if value[key] else None
        return value

    def recent(self):
        with self.connect() as db:
            rows = db.execute('SELECT id, created, question, mode, status FROM runs ORDER BY created DESC LIMIT 20').fetchall()
        return [dict(row) for row in rows]
