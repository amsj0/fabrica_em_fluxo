"""Motor puro: sem persistência, UI, rede ou estado aleatório global."""
import copy
import hashlib
import math
import random
from .schema import Scenario, Decision


def ratio(a, b):
    return a / b if b else None


def initial(s):
    return {'budget': s.budget, 'lines': {l.id: {'capacity': l.capacity,
        'materials': l.initial_materials, 'stock': l.initial_stock,
        'backlog': l.initial_backlog} for l in s.lines}}


def shocks(s, month, line):
    # Independent streams keep paired experiments aligned when decisions change.
    seed = hashlib.sha256(f'{s.seed}:{month}:{line}'.encode()).digest()
    rng = random.Random(int.from_bytes(seed, 'big'))
    return {'demand_factor': rng.uniform(.85, 1.15),
            'downtime': rng.uniform(0, .12), 'delivery_factor': rng.uniform(.8, 1)} if s.shocks else {
            'demand_factor': 1., 'downtime': 0., 'delivery_factor': 1.}


def advance(s, state, policy, month):
    state = copy.deepcopy(state)
    traces = []
    for l in s.lines:
        before = state['lines'][l.id].copy()
        p = policy[l.id]
        shock = shocks(s, month, l.id)
        demand = math.floor(l.demand[0 if len(l.demand) == 1 else month-1] * shock['demand_factor'])
        delivered = p.materials_order * shock['delivery_factor']
        materials = before['materials'] + delivered
        nominal = before['capacity'] * p.shifts
        availability = max(0., min(1., l.availability + .08*p.maintenance - shock['downtime'])) * (1-.15*p.maintenance)
        equipment_limit = math.floor(nominal*availability)
        labor_limit = math.floor(p.workers*p.shifts*l.productivity)
        material_limit = math.floor(materials/l.material_per_unit + 1e-9)
        limits = {'plano': p.planned, 'equipamento': equipment_limit,
                  'equipe': labor_limit, 'materiais': material_limit}
        gross = min(limits.values())
        defect_rate = min(.5, l.defect_rate*(1-.5*p.maintenance) + .05*shock['downtime'])
        scrap = math.floor(gross*defect_rate)
        good = gross-scrap
        consumed = gross*l.material_per_unit
        owed = before['backlog'] + demand
        shipped = min(owed, before['stock']+good)
        shipped_backlog = min(before['backlog'], shipped)
        shipped_current = shipped-shipped_backlog
        remaining = owed-shipped
        stock = before['stock']+good-shipped
        payroll = p.workers*p.shifts*l.wage
        maintenance_cost = p.maintenance*l.maintenance_cost
        production_cost = gross*l.variable_cost
        holding = stock*l.holding_cost
        operating_cost = payroll + maintenance_cost + production_cost + holding + l.fixed_cost + consumed*l.material_cost
        purchase_cost = delivered*l.material_cost
        investment_cost = p.investment*l.investment_cost
        cash_out = operating_cost - consumed*l.material_cost + purchase_cost + investment_cost
        revenue = shipped*l.sale_price
        state['lines'][l.id] = {'capacity': before['capacity']+p.investment,
            'materials': max(0., materials-consumed), 'stock': stock,
            'backlog': remaining if s.demand_mode == 'backlog' else 0}
        traces.append({'line': l.id, 'name': l.name, 'opening': before,
            'closing': state['lines'][l.id].copy(), 'decision': p.model_dump(), 'shocks': shock,
            'demand': demand, 'owed': owed, 'planned': p.planned, 'nominal_capacity': nominal,
            'equipment_limit': equipment_limit, 'labor_limit': labor_limit, 'material_limit': material_limit,
            'availability': availability, 'gross': gross, 'good': good, 'scrap': scrap,
            'scrap_rate': ratio(scrap, gross), 'quality': ratio(good, gross),
            'utilization': ratio(gross, equipment_limit), 'defect_parameter': defect_rate,
            'delivered': delivered, 'consumed': consumed, 'shipped': shipped,
            'shipped_current': shipped_current, 'shipped_backlog': shipped_backlog,
            'service': ratio(shipped_current, demand), 'fulfillment': ratio(shipped, owed),
            'lost': remaining if s.demand_mode == 'lost' else 0,
            'stock': stock, 'backlog': state['lines'][l.id]['backlog'],
            'payroll': payroll, 'fixed_cost': l.fixed_cost, 'maintenance_cost': maintenance_cost,
            'production_cost': production_cost, 'holding_cost': holding,
            'material_consumption_cost': consumed*l.material_cost,
            'purchase_cost': purchase_cost, 'investment_cost': investment_cost,
            'operating_cost': operating_cost, 'unit_cost': ratio(operating_cost, good),
            'cash_out': cash_out, 'revenue': revenue,
            'constraints': [k for k, v in limits.items() if v == gross]})
    sums = ['demand', 'owed', 'planned', 'nominal_capacity', 'equipment_limit', 'gross', 'good', 'scrap',
            'shipped', 'shipped_current', 'lost', 'stock', 'backlog', 'operating_cost', 'cash_out', 'revenue']
    row = {k: sum(t[k] for t in traces) for k in sums}
    row.update(month=month, budget_open=state['budget'], traces=traces)
    state['budget'] += row['revenue']-row['cash_out']
    row.update(budget=state['budget'], funding_gap=max(0., -state['budget']),
               service=ratio(row['shipped_current'], row['demand']),
               fulfillment=ratio(row['shipped'], row['owed']),
               availability=ratio(sum(t['nominal_capacity']*t['availability'] for t in traces), row['nominal_capacity']),
               utilization=ratio(row['gross'], row['equipment_limit']),
               quality=ratio(row['good'], row['gross']), scrap_rate=ratio(row['scrap'], row['gross']),
               unit_cost=ratio(row['operating_cost'], row['good']))
    return state, row


def score(row, goals):
    terms = []
    for g in goals:
        value = row[g.indicator]
        distance = None if value is None else (max(0, value-g.target) if g.kind == 'upper' else
                    max(0, g.target-value) if g.kind == 'lower' else abs(value-g.target)) / g.scale
        utility = 0. if distance is None else 1/(1+distance)
        terms.append({**g.model_dump(), 'value': value, 'distance': distance, 'utility': utility,
                      'contribution': g.weight*utility})
    return sum(t['contribution'] for t in terms)/sum(g.weight for g in goals), terms


def choose(s, state, current, month):
    """One coordinate sweep, evaluating a two-month repeat-policy horizon.

    Current resource shocks are observed; next-month forecast has no shocks.
    Baseline is retained on ties. This is not a global optimization.
    """
    horizon = min(2, s.months-month+1)
    forecast = s.model_copy(update={'shocks': False})
    candidates = []

    def evaluate(policy, reason):
        projected, r = advance(s, state, policy, month)
        value, terms = score(r, s.goals)
        if horizon == 2:
            _, future = advance(forecast, projected, policy, month+1)
            value += score(future, s.goals)[0]
        value /= horizon
        candidates.append({'reason': reason, 'score': value,
                           'policy': {k: p.model_dump() for k, p in policy.items()},
                           'current_terms': terms})
        return value

    chosen = copy.deepcopy(current)
    baseline = best = evaluate(chosen, 'Política anterior')
    for l in s.lines:
        for key, step, low, high in [('workers', 2, 0, 200), ('shifts', 1, 1, 3),
            ('maintenance', .25, 0, 1), ('materials_order', l.capacity*l.material_per_unit*.25, 0, 1e7),
            ('investment', l.capacity*.1, 0, 10000), ('planned', max(1, int(l.capacity*.25)), 0, 1000000)]:
            anchor = copy.deepcopy(chosen)
            for direction in (-1, 1):
                raw = anchor[l.id].model_dump()
                raw[key] = max(low, min(high, raw[key]+direction*step))
                candidate = copy.deepcopy(anchor)
                candidate[l.id] = Decision.model_validate(raw)
                value = evaluate(candidate, f'{l.name}: {key} → {raw[key]}')
                if value > best+1e-12:
                    best, chosen = value, candidate
    return chosen, {'baseline_score': baseline, 'chosen_score': best, 'horizon': horizon,
        'reason': 'Melhoria entre alternativas locais avaliadas' if best > baseline+1e-12 else 'Política anterior mantida: nenhuma melhoria estrita',
        'method': 'Uma passagem por coordenadas; próximo mês sem choques; sem garantia de ótimo global.',
        'candidates': candidates}


def simulate(scenario):
    s = Scenario.model_validate(scenario.model_dump() if isinstance(scenario, Scenario) else scenario)
    state = initial(s)
    rows = []
    policy = s.policy
    for month in range(1, s.months+1):
        decision = {'reason': 'Política fixa configurada', 'method': 'fixed'}
        if s.policy_mode == 'manual':
            policy = s.manual[month-1]
            decision = {'reason': f'Sequência manual: período {month}', 'method': 'manual'}
        elif s.policy_mode == 'endogenous':
            policy, decision = choose(s, state, policy, month)
        state, row = advance(s, state, policy, month)
        absolute_month = int(s.start[:4])*12+int(s.start[5:])-1+month-1
        row['period'] = f'{absolute_month//12:04d}-{absolute_month%12+1:02d}'
        row['score'], row['goal_terms'] = score(row, s.goals)
        row['decision'] = decision
        rows.append(row)
    return {'version': '1.0.0', 'initial': initial(s), 'rows': rows, 'final': state}
