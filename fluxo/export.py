import csv
import io
import json
import zipfile
from .schema import Scenario
from .service import canonical, digest, verify
from .storage import ROOT


def csv_bytes(rows):
    columns = list(dict.fromkeys(k for r in rows for k, v in r.items() if not isinstance(v, (list, dict))))
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode('utf-8-sig')


def policy_rows(result):
    return [{'month': r['month'], 'period': r['period'], 'line': t['line'], **t['decision']}
            for r in result['rows'] for t in r['traces']]


def export_package(bundle):
    scenario = Scenario.model_validate(bundle['scenario'])
    verify(bundle['result'], scenario)
    if digest(bundle['result']) != bundle['hashes']['result'] or digest(bundle['scenario']) != bundle['hashes']['scenario']:
        raise ValueError('Hashes inconsistentes: exportação recusada.')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('scenario.json', canonical(bundle['scenario']))
        archive.writestr('execution.json', canonical(bundle))
        archive.writestr('indicators.csv', csv_bytes(bundle['result']['rows']))
        archive.writestr('policies.csv', csv_bytes(policy_rows(bundle['result'])))
        archive.writestr('lines.csv', csv_bytes([{'month': r['month'], 'period': r['period'], **t}
            for r in bundle['result']['rows'] for t in r['traces']]))
        for name in ('docs/modelo.md', 'README.md', 'requirements.txt'):
            path = ROOT/name
            if path.exists():
                archive.write(path, name)
    return out.getvalue()


def import_scenario(data):
    if len(data) > 10_000_000:
        raise ValueError('Arquivo excede 10 MB.')
    try:
        if data[:2] == b'PK':
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.getinfo('scenario.json')
                if info.file_size > 1_000_000:
                    raise ValueError('Cenário excede 1 MB.')
                data = archive.read(info)
        return Scenario.model_validate_json(data)
    except (KeyError, zipfile.BadZipFile, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Arquivo de cenário inválido.') from exc
