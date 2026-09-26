import json
import sqlite3
import uuid
from contextlib import closing


class Store:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, state TEXT NOT NULL)')

    def create(self, state):
        state['id'] = uuid.uuid4().hex
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO runs VALUES (?, ?)', (state['id'], json.dumps(state)))
        return state

    def get(self, run_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute('SELECT state FROM runs WHERE id = ?', (run_id,)).fetchone()
        if row is None:
            raise KeyError('Run not found.')
        return json.loads(row[0])

    def save(self, run_id, state):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE runs SET state = ? WHERE id = ?', (json.dumps(state), run_id))
