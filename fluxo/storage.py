import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .schema import Scenario

ROOT = Path(__file__).resolve().parents[1]


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, home=None):
        self.home = Path(home or os.environ.get('FLUXO_HOME', ROOT/'runtime'))
        self.home.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.home/'fluxo.sqlite')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS revisions (
            id TEXT PRIMARY KEY, parent TEXT REFERENCES revisions(id), created TEXT, scenario TEXT);
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, revision TEXT REFERENCES revisions(id), created TEXT,
            status TEXT, bundle TEXT, error TEXT);
        ''')
        self.db.commit()

    def save(self, scenario, parent=None):
        s = Scenario.model_validate(scenario.model_dump() if isinstance(scenario, Scenario) else scenario)
        ident = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO revisions VALUES(?,?,?,?)',
                            (ident, parent, stamp(), s.model_dump_json()))
        return ident

    def revisions(self):
        return [dict(r) | {'scenario': json.loads(r['scenario'])} for r in
                self.db.execute('SELECT * FROM revisions ORDER BY created DESC')]

    def scenario(self, revision):
        row = self.db.execute('SELECT scenario FROM revisions WHERE id=?', (revision,)).fetchone()
        if row is None:
            raise ValueError('Cenário não encontrado.')
        return Scenario.model_validate_json(row['scenario'])

    def start(self, revision):
        ident = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)', (ident, revision, stamp(), 'running', None, None))
        return ident

    def finish(self, ident, bundle=None, error=None):
        with self.db:
            self.db.execute('UPDATE runs SET status=?,bundle=?,error=? WHERE id=?',
                ('failed' if error else 'complete', json.dumps(bundle, ensure_ascii=False, allow_nan=False), error, ident))

    def runs(self):
        return [dict(r) for r in self.db.execute('''SELECT r.id,r.revision,r.created,r.status,r.error,
            v.scenario FROM runs r JOIN revisions v ON r.revision=v.id ORDER BY r.created DESC''')]

    def bundle(self, ident):
        row = self.db.execute('SELECT * FROM runs WHERE id=?', (ident,)).fetchone()
        if row is None or row['status'] != 'complete':
            raise ValueError('Execução concluída não encontrada.')
        return json.loads(row['bundle'])

    def close(self):
        self.db.close()
