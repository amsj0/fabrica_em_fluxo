from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Decision(Strict):
    workers: int = Field(default=10, ge=0, le=200, strict=True)
    shifts: int = Field(default=1, ge=1, le=3, strict=True)
    maintenance: float = Field(default=.4, ge=0, le=1)
    materials_order: float = Field(default=1100, ge=0, le=1e7)
    investment: float = Field(default=0, ge=0, le=10000)
    planned: int = Field(default=950, ge=0, le=1000000, strict=True)


class Line(Strict):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,23}$')
    name: str = Field(min_length=1, max_length=80)
    capacity: float = Field(default=1000, gt=0, le=1e6)
    productivity: float = Field(default=100, gt=0, le=1e5)
    availability: float = Field(default=.92, ge=0, le=1)
    defect_rate: float = Field(default=.03, ge=0, le=.5)
    material_per_unit: float = Field(default=1, gt=0, le=10000)
    initial_materials: float = Field(default=500, ge=0, le=1e8)
    initial_stock: int = Field(default=100, ge=0, le=1000000, strict=True)
    initial_backlog: int = Field(default=0, ge=0, le=1000000, strict=True)
    demand: list[Annotated[int, Field(strict=True, ge=0, le=1000000)]] = Field(default_factory=lambda: [900], min_length=1, max_length=36)
    material_cost: float = Field(default=12, ge=0, le=1e6)
    wage: float = Field(default=2200, ge=0, le=1e6)
    fixed_cost: float = Field(default=3000, ge=0, le=1e8)
    variable_cost: float = Field(default=4, ge=0, le=1e6)
    maintenance_cost: float = Field(default=1500, ge=0, le=1e7)
    investment_cost: float = Field(default=100, ge=0, le=1e6)
    holding_cost: float = Field(default=1, ge=0, le=1e6)
    sale_price: float = Field(default=55, ge=0, le=1e7)

    @model_validator(mode='after')
    def valid_demand(self):
        if any(type(x) is not int or not 0 <= x <= 1000000 for x in self.demand):
            raise ValueError('Pedidos devem ser inteiros entre 0 e 1.000.000.')
        return self


class Goal(Strict):
    indicator: Literal['service', 'backlog', 'stock', 'unit_cost', 'budget', 'scrap_rate', 'utilization']
    kind: Literal['target', 'upper', 'lower'] = 'target'
    target: float = Field(ge=-1e14, le=1e14)
    weight: float = Field(default=1, ge=0, le=100)
    scale: float = Field(default=1, gt=0, le=1e12)

    @model_validator(mode='after')
    def valid_target(self):
        if self.indicator in ('service', 'scrap_rate', 'utilization') and not 0 <= self.target <= 1:
            raise ValueError('Metas de proporção devem estar entre 0 e 1.')
        if self.indicator not in ('budget',) and self.target < 0:
            raise ValueError('Esta meta não pode ser negativa.')
        return self


class Scenario(Strict):
    name: str = Field(default='Duas células · cenário base', min_length=1, max_length=120)
    description: str = Field(default='', max_length=4000)
    start: str = Field(default='2026-01', pattern=r'^\d{4}-\d{2}$')
    months: int = Field(default=6, ge=1, le=36, strict=True)
    seed: int = Field(default=42, ge=0, le=2**32-1, strict=True)
    shocks: bool = False
    demand_mode: Literal['backlog', 'lost'] = 'backlog'
    budget: float = Field(default=200000, ge=0, le=1e12)
    policy_mode: Literal['fixed', 'manual', 'endogenous'] = 'fixed'
    lines: list[Line] = Field(min_length=1, max_length=6)
    policy: dict[str, Decision]
    manual: list[dict[str, Decision]] = Field(default_factory=list, max_length=36)
    goals: list[Goal] = Field(default_factory=lambda: [
        Goal(indicator='service', kind='lower', target=.95, weight=3, scale=.1),
        Goal(indicator='unit_cost', kind='upper', target=48, scale=10),
        Goal(indicator='budget', kind='lower', target=100000, scale=100000),
    ], min_length=1, max_length=7)

    @model_validator(mode='after')
    def coherent(self):
        date.fromisoformat(self.start+'-01')
        if not 1900 <= int(self.start[:4]) <= 2100:
            raise ValueError('Ano inicial deve estar entre 1900 e 2100.')
        ids = {line.id for line in self.lines}
        if len(ids) != len(self.lines):
            raise ValueError('Identificadores de células devem ser únicos.')
        for policy in [self.policy, *self.manual]:
            if set(policy) != ids:
                raise ValueError('Cada política deve conter exatamente todas as células.')
        if self.policy_mode == 'manual' and len(self.manual) != self.months:
            raise ValueError('Informe uma política manual completa para cada mês.')
        if any(len(line.demand) not in (1, self.months) for line in self.lines):
            raise ValueError('Pedidos: um valor recorrente ou um valor por mês.')
        if self.demand_mode == 'lost' and any(line.initial_backlog for line in self.lines):
            raise ValueError('Demanda perdida exige backlog inicial zero.')
        if sum(g.weight for g in self.goals) <= 0 or len({g.indicator for g in self.goals}) != len(self.goals):
            raise ValueError('Metas únicas e soma dos pesos positiva são obrigatórias.')
        return self


def demo():
    return Scenario(lines=[Line(id='alpha', name='Célula Alfa'),
                           Line(id='beta', name='Célula Beta', capacity=750, demand=[650],
                                initial_materials=300, productivity=90)],
                    policy={'alpha': Decision(), 'beta': Decision(workers=8, planned=720, materials_order=800)})
