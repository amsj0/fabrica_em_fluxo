import hashlib
import json
import math
import platform
from .engine import simulate
from .storage import ROOT, stamp


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def verify(result, scenario):
    if len(result['rows']) != scenario.months:
        raise ValueError('Horizonte incorreto.')
    canonical(result)  # Reject NaN/Infinity.

    def equal(a, b):
        if not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6):
            raise ValueError('Balanço inconsistente.')

    previous = result['initial']
    for month, r in enumerate(result['rows'], 1):
        if r['month'] != month or {t['line'] for t in r['traces']} != {l.id for l in scenario.lines}:
            raise ValueError('Período ou células inconsistentes.')
        equal(previous['budget'], r['budget_open'])
        equal(r['budget'], r['budget_open']+r['revenue']-r['cash_out'])
        next_lines = {}
        for t in r['traces']:
            if t['opening'] != previous['lines'][t['line']]:
                raise ValueError('Continuidade do estado inválida.')
            if t['gross'] < 0 or t['gross'] > min(t['planned'], t['equipment_limit'], t['labor_limit'], t['material_limit']):
                raise ValueError('Limite de produção violado.')
            equal(t['gross'], t['good']+t['scrap'])
            equal(t['opening']['stock']+t['good'], t['stock']+t['shipped'])
            equal(t['opening']['backlog']+t['demand'], t['shipped']+t['backlog']+t['lost'])
            equal(t['opening']['materials']+t['delivered'], t['closing']['materials']+t['consumed'])
            if any(t['closing'][k] < 0 for k in ('materials', 'stock', 'backlog', 'capacity')):
                raise ValueError('Estado negativo.')
            next_lines[t['line']] = t['closing']
        previous = {'budget': r['budget'], 'lines': next_lines}
    if previous != result['final']:
        raise ValueError('Estado final inconsistente.')


def execute(store, revision):
    scenario = store.scenario(revision)
    ident = store.start(revision)
    try:
        result = simulate(scenario)
        verify(result, scenario)
        source = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'fluxo').glob('*.py')}
        bundle = {'run_id': ident, 'revision': revision, 'created': stamp(),
                  'scenario': scenario.model_dump(), 'result': result,
                  'classification': 'Dados sintéticos; simulação educativa não validada industrialmente.',
                  'hashes': {'scenario': digest(scenario.model_dump()), 'result': digest(result), 'source': source},
                  'environment': {'python': platform.python_version(), 'model': result['version']}}
        store.finish(ident, bundle=bundle)
        return bundle
    except Exception as exc:
        store.finish(ident, error=f'{type(exc).__name__}: {exc}')
        raise


def comparison(a, b):
    # Show every assumption change; only policy/goals/name/description are intended interventions.
    diffs = {k: {'A': a['scenario'][k], 'B': b['scenario'][k]} for k in a['scenario'] if a['scenario'][k] != b['scenario'][k]}
    warnings = [k for k in diffs if k not in ('name', 'description', 'policy', 'manual', 'policy_mode', 'goals')]
    return diffs, warnings
