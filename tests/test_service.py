import copy
import csv
import io
import json
import subprocess
import sys
import zipfile
import pytest
from fluxo.schema import demo
from fluxo.storage import Store, ROOT
from fluxo.service import execute, comparison, digest, verify
from fluxo.export import export_package, import_scenario


def test_persistence_revisions_export_and_reproduction(tmp_path):
    store = Store(tmp_path)
    scenario = demo()
    revision = store.save(scenario)
    bundle = execute(store, revision)
    variation = scenario.model_dump()
    variation['policy']['alpha']['workers'] = 12
    child = store.save(variation, parent=revision)
    second = execute(store, child)
    assert comparison(bundle, second)[0].keys() == {'policy'}
    assert comparison(bundle, second)[1] == []
    assert store.bundle(bundle['run_id']) == bundle
    assert store.revisions()[0]['parent'] == revision
    data = export_package(bundle)
    assert import_scenario(data) == scenario
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        exported = json.loads(archive.read('execution.json'))
        assert exported == bundle
        rows = list(csv.DictReader(io.StringIO(archive.read('indicators.csv').decode('utf-8-sig'))))
        assert len(rows) == scenario.months
        for original, exported in zip(bundle['result']['rows'], rows):
            for key, value in original.items():
                if isinstance(value, (float, int)):
                    assert float(exported[key]) == value
                elif value is None:
                    assert exported[key] == ''
        policies = list(csv.DictReader(io.StringIO(archive.read('policies.csv').decode('utf-8-sig'))))
        assert len(policies) == scenario.months*len(scenario.lines)
        assert float(policies[0]['workers']) == scenario.policy['alpha'].workers
    assert digest(execute(store, revision)['result']) == bundle['hashes']['result']
    store.close()
    code = 'from fluxo.storage import Store; import sys; s=Store(sys.argv[1]); assert s.bundle(sys.argv[2])["revision"]==sys.argv[3]; s.close()'
    subprocess.run([sys.executable, '-c', code, str(tmp_path), bundle['run_id'], revision], cwd=ROOT, check=True)


def test_failed_run_is_recorded(tmp_path, monkeypatch):
    import fluxo.service as service
    store = Store(tmp_path)
    def fail(*args):
        raise RuntimeError('Teste de falha')
    monkeypatch.setattr(service, 'simulate', fail)
    with pytest.raises(RuntimeError): execute(store, store.save(demo()))
    assert store.runs()[0]['status'] == 'failed'
    store.close()


def test_corrupt_export_and_invalid_import(tmp_path):
    store = Store(tmp_path)
    bundle = execute(store, store.save(demo()))
    corrupt = copy.deepcopy(bundle)
    corrupt['result']['rows'][0]['good'] += 1
    with pytest.raises(ValueError): export_package(corrupt)
    corrupt = copy.deepcopy(bundle)
    corrupt['result']['rows'][0]['traces'][0]['stock'] += 1
    with pytest.raises(ValueError): verify(corrupt['result'], demo())
    for data in (b'not JSON', b'PKinvalid', b'{}'):
        with pytest.raises(ValueError): import_scenario(data)
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z: z.writestr('other.json', '{}')
    with pytest.raises(ValueError): import_scenario(out.getvalue())
    store.close()


def test_compare_reports_changed_shocks_and_dates(tmp_path):
    store = Store(tmp_path)
    a = execute(store, store.save(demo()))
    raw = demo().model_dump() | {'seed': 2, 'start': '2027-01', 'months': 2}
    b = execute(store, store.save(raw))
    assert set(comparison(a, b)[1]) == {'seed', 'start', 'months'}
    store.close()
