import copy
import pytest
from fluxo.schema import Scenario, demo
from fluxo.engine import simulate


def case(**decision):
    raw = demo().model_dump()
    raw['months'] = 1
    raw['lines'] = raw['lines'][:1]
    raw['policy'] = {'alpha': raw['policy']['alpha'] | {'maintenance': 0, 'materials_order': 0} | decision}
    raw['lines'][0].update(availability=1, defect_rate=0, initial_materials=10000, initial_stock=0)
    return raw


@pytest.mark.parametrize('changes, line_changes, expected, constraint', [
    ({'planned': 5000}, {}, 1000, 'equipamento'),
    ({'workers': 2}, {}, 200, 'equipe'),
    ({}, {'initial_materials': 55, 'material_per_unit': 2}, 27, 'materiais'),
    ({'planned': 17}, {}, 17, 'plano'),
    ({'workers': 0}, {}, 0, 'equipe'),
    ({}, {'availability': 0}, 0, 'equipamento'),
])
def test_limits(changes, line_changes, expected, constraint):
    raw = case(**changes)
    raw['lines'][0].update(line_changes)
    t = simulate(raw)['rows'][0]['traces'][0]
    assert t['gross'] == expected
    assert constraint in t['constraints']


def test_balances_scrap_backlog_and_costs():
    raw = case(planned=500)
    raw['lines'][0].update(defect_rate=.1, demand=[700], initial_stock=50, initial_backlog=100)
    r = simulate(raw)['rows'][0]
    t = r['traces'][0]
    assert (t['good'], t['scrap'], t['shipped'], t['backlog'], t['stock']) == (450, 50, 500, 300, 0)
    assert t['shipped_current'] == 400
    assert t['service'] == pytest.approx(400/700)
    assert t['closing']['materials'] == 9500
    assert t['unit_cost'] == pytest.approx(t['operating_cost']/450)
    assert r['budget'] == pytest.approx(raw['budget']+r['revenue']-r['cash_out'])


def test_lost_sales_and_zero_denominators():
    raw = case(planned=0)
    raw['demand_mode'] = 'lost'
    r = simulate(raw)['rows'][0]
    assert (r['lost'], r['backlog'], r['unit_cost'], r['quality']) == (900, 0, None, None)
    raw['lines'][0]['demand'] = [0]
    assert simulate(raw)['rows'][0]['service'] is None


def test_investment_arrives_next_month_and_material_purchase_cash():
    raw = case(planned=5000, workers=100, investment=100, materials_order=500)
    raw['months'] = 2
    rows = simulate(raw)['rows']
    assert [r['gross'] for r in rows] == [1000, 1100]
    assert rows[1]['traces'][0]['closing']['capacity'] == 1200
    t = rows[0]['traces'][0]
    assert t['cash_out'] == pytest.approx(t['operating_cost']-t['material_consumption_cost']+t['purchase_cost']+t['investment_cost'])


def test_deterministic_shocks_common_streams_and_no_mutation():
    raw = demo().model_dump() | {'shocks': True}
    before = copy.deepcopy(raw)
    first = simulate(raw)
    assert first == simulate(raw) and raw == before
    raw['policy']['alpha']['workers'] = 0
    second = simulate(raw)
    assert [[t['shocks'] for t in r['traces']] for r in first['rows']] == [[t['shocks'] for t in r['traces']] for r in second['rows']]
    raw['seed'] += 1
    assert simulate(raw)['rows'][0]['traces'][0]['shocks'] != first['rows'][0]['traces'][0]['shocks']


def test_manual_matches_fixed_except_explanation():
    raw = demo().model_dump()
    fixed = simulate(raw)
    raw.update(policy_mode='manual', manual=[copy.deepcopy(raw['policy']) for _ in range(raw['months'])])
    manual = simulate(raw)
    for a, b in zip(fixed['rows'], manual['rows']):
        a.pop('decision'); b.pop('decision')
        assert a == b


@pytest.mark.parametrize('update', [
    {'months': 0}, {'months': 1.5}, {'seed': -1}, {'start': '2026-13'}, {'policy_mode': 'manual'},
    {'budget': float('nan')}, {'unknown': 2}, {'policy': {}},
    {'goals': [{'indicator': 'service', 'target': 2}]},
    {'goals': [{'indicator': 'service', 'target': .9, 'weight': 0}]},
])
def test_invalid_scenarios(update):
    with pytest.raises(ValueError):
        Scenario.model_validate(demo().model_dump() | update)


def test_validation_nested_and_months():
    raw = case()
    raw['policy']['alpha']['workers'] = -1
    with pytest.raises(ValueError): simulate(raw)
    raw = case()
    raw['lines'][0]['demand'] = [1, 2]
    with pytest.raises(ValueError): simulate(raw)


@pytest.mark.parametrize('demand', [[True], [1.5], ['5'], [-1], [1000001]])
def test_demand_requires_bounded_integers(demand):
    raw = case()
    raw['lines'][0]['demand'] = demand
    with pytest.raises(ValueError): simulate(raw)


def test_maintenance_reduces_time_and_scrap():
    raw = case(planned=2000, maintenance=1)
    raw['lines'][0]['defect_rate'] = .1
    t = simulate(raw)['rows'][0]['traces'][0]
    assert t['availability'] == .85
    assert t['gross'] == 850
    assert t['scrap'] == 42
    assert t['maintenance_cost'] == raw['lines'][0]['maintenance_cost']


def test_endogenous_retains_baseline_and_explains_goals():
    raw = demo().model_dump() | {'months': 2, 'policy_mode': 'endogenous', 'shocks': True}
    result = simulate(raw)
    assert result == simulate(raw)
    for r in result['rows']:
        assert r['decision']['chosen_score'] >= r['decision']['baseline_score']
        assert len(r['decision']['candidates']) == 25
        assert all('contribution' in t for t in r['goal_terms'])
    raw['goals'] = [{'indicator': 'budget', 'target': -1e12, 'kind': 'lower'}]
    assert simulate(raw)['rows'][0]['traces'][0]['decision'] == raw['policy']['alpha']


def test_monthly_conservation_under_shocks_and_deficit():
    raw = demo().model_dump() | {'months': 36, 'shocks': True, 'budget': 0}
    raw['policy']['alpha']['workers'] = 200
    result = simulate(raw)
    for r in result['rows']:
        assert r['budget'] == pytest.approx(r['budget_open']+r['revenue']-r['cash_out'])
        for t in r['traces']:
            assert t['opening']['stock']+t['good'] == t['shipped']+t['stock']
            assert t['opening']['backlog']+t['demand'] == t['shipped']+t['backlog']+t['lost']
            assert t['opening']['materials']+t['delivered'] == pytest.approx(t['closing']['materials']+t['consumed'])
            assert t['gross'] == t['good']+t['scrap']
    assert result['rows'][-1]['funding_gap'] > 0
