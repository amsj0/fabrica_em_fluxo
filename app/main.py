from pathlib import Path
import copy
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fluxo.schema import Scenario, demo
from fluxo.storage import ROOT, Store
from fluxo.service import execute, comparison
from fluxo.export import csv_bytes, export_package, import_scenario

st.set_page_config(page_title='Fábrica em Fluxo', page_icon='🏭', layout='wide')
st.markdown('''<style>
.block-container {max-width:1480px;padding-top:1.6rem;padding-bottom:4rem}
body {background-color:#f4f3ed;background-image:linear-gradient(rgba(32,45,39,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(32,45,39,.025) 1px,transparent 1px);background-size:24px 24px}
h1,h2,h3 {letter-spacing:0}
[data-testid="stSidebar"] {background:#202d27;border-right:4px solid #e66b3d}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"], [data-testid="stSidebar"] label, [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color:#e8ece4}
[data-testid="stSidebar"] h2 {font-family:Georgia,serif;color:#fff;font-size:1.35rem}
[data-testid="stSidebar"] hr {border-color:#43534a}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {background:#34443b;border-color:#53665a;color:#fff}
[data-testid="stSidebar"] [data-testid="stFileUploader"] section {background:#27372f;border-color:#53665a}
[data-testid="stBaseButton-primary"] {background:#bd4d27;border-color:#bd4d27}
[data-testid="stBaseButton-primary"]:hover {background:#9f3d20;border-color:#9f3d20}
[data-testid="stMetric"] {border:0;border-top:3px solid #e66b3d;border-radius:2px;padding:16px 18px;background:#fff;box-shadow:0 2px 8px rgba(32,45,39,.05)}
[data-testid="stMetricValue"] {font-size:1.8rem;color:#202d27}
.masthead {display:flex;align-items:flex-end;justify-content:space-between;gap:2rem;padding:1rem 0 1.5rem;border-bottom:1px solid #c9cec4;margin-bottom:1.2rem}
.masthead h1 {font-family:Georgia,serif;color:#202d27;font-size:2.6rem;font-weight:500;margin:.25rem 0 .45rem}
.masthead p {color:#56645b;max-width:700px;margin:0;font-size:1rem}
.eyebrow {font-size:.72rem;font-weight:800;letter-spacing:1.5px;color:#bd4d27}
.masthead-meta {min-width:180px;border-left:1px solid #c9cec4;padding:.45rem 0 .45rem 1rem;color:#56645b;font-size:.72rem;font-weight:700;line-height:1.7}
.masthead-meta span {display:block;color:#202d27;font-size:.82rem}
[data-testid="stRadio"] [role="radiogroup"] {gap:.35rem;flex-wrap:nowrap;overflow-x:auto;border-bottom:2px solid #202d27;padding-bottom:.8rem}
[data-testid="stRadio"] label {background:#e7e8df;border:1px solid #d5d8ce;border-radius:3px;padding:.38rem .55rem;margin:0;font-size:.88rem;white-space:nowrap}
[data-testid="stRadio"] label > div:first-child {display:none}
[data-testid="stRadio"] label:has(input:checked) {background:#202d27;border-color:#202d27;color:#fff}
[data-testid="stRadio"] label:has(input:checked) p {color:#fff}
[data-testid="stRadio"] input {accent-color:#e66b3d}
[data-testid="stDataFrame"], [data-testid="stTable"] {border:1px solid #d5d8ce}
div[data-testid="stExpander"] {border-radius:3px;border-color:#d5d8ce}
@media (max-width:640px) {
    .masthead {display:block}
    .masthead h1 {font-size:2.2rem;overflow-wrap:normal;word-break:normal}
    .masthead-meta {margin-top:1rem;border-left:0;border-top:1px solid #c9cec4;padding:.7rem 0 0}
}
</style>''', unsafe_allow_html=True)

store = Store()
if 'scenario' not in st.session_state:
    st.session_state.scenario = demo().model_dump()
    st.session_state.revision = None
    st.session_state.parent = None
    st.session_state.editor_version = 0
if 'editor_source' not in st.session_state:
    st.session_state.editor_source = copy.deepcopy(st.session_state.scenario)


def set_scenario(raw, revision=None, parent=None):
    st.session_state.scenario = raw
    st.session_state.editor_source = copy.deepcopy(raw)
    st.session_state.revision = revision
    st.session_state.parent = parent
    st.session_state.editor_version += 1
    st.session_state.pop('bundle', None)


def load(raw, revision=None, parent=None):
    set_scenario(raw, revision, parent)
    store.close()
    st.rerun()


def format_value(v, percent=False):
    if v is None:
        return '—'
    return f'{v*100:.1f}%' if percent else f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


LABELS = {'good': 'Produção boa', 'gross': 'Produção realizada (bruta)', 'planned': 'Produção planejada',
    'service': 'Nível de serviço', 'backlog': 'Pedidos em atraso', 'stock': 'Estoque acabado',
    'unit_cost': 'Custo por unidade boa (R$)', 'budget': 'Saldo do orçamento (R$)', 'scrap_rate': 'Refugo',
    'utilization': 'Utilização', 'availability': 'Disponibilidade', 'quality': 'Qualidade',
    'demand': 'Pedidos novos', 'shipped': 'Entregas', 'lost': 'Demanda perdida', 'funding_gap': 'Necessidade de recursos (R$)'}
PERCENT = {'service', 'scrap_rate', 'utilization', 'availability', 'quality'}
MODE = {'fixed': 'Fixa', 'manual': 'Manual por mês', 'endogenous': 'Busca local por metas'}
POLICY_CONFIG = {
    'line': st.column_config.TextColumn('Célula', disabled=True),
    'month': st.column_config.NumberColumn('Mês', disabled=True),
    'workers': st.column_config.NumberColumn('Pessoas por turno', min_value=0, max_value=200, step=1),
    'shifts': st.column_config.NumberColumn('Turnos', min_value=1, max_value=3, step=1),
    'maintenance': st.column_config.NumberColumn('Manutenção · 0 a 1', min_value=0., max_value=1., step=.05),
    'materials_order': st.column_config.NumberColumn('Reposição · material', min_value=0., max_value=1e7),
    'investment': st.column_config.NumberColumn('Capacidade adicional', min_value=0., max_value=10000.),
    'planned': st.column_config.NumberColumn('Plano · unidades brutas', min_value=0, max_value=1000000, step=1),
}

with st.sidebar:
    st.markdown('## Fábrica em Fluxo')
    st.caption('PAINEL DE OPERAÇÕES')
    st.divider()
    demos = sorted((ROOT/'data/demo').glob('*.json'))
    if demos:
        demo_file = st.selectbox('Experimentos sintéticos', demos, format_func=lambda p: p.stem.replace('_', ' ').title())
        if st.button('Carregar demonstração', use_container_width=True):
            load(import_scenario(demo_file.read_bytes()).model_dump())
    revisions = store.revisions()
    if revisions:
        saved = st.selectbox('Cenários salvos', revisions,
            format_func=lambda r: r['scenario']['name']+' · '+r['id'][:8])
        if st.button('Retomar cenário', use_container_width=True):
            load(saved['scenario'], revision=saved['id'], parent=saved['parent'])
    runs = store.runs()
    completed = [r for r in runs if r['status'] == 'complete']
    if completed:
        selected = st.selectbox('Execuções salvas', completed,
            format_func=lambda r: json.loads(r['scenario'])['name']+' · '+r['id'][:8])
        if st.button('Abrir resultado', use_container_width=True):
            st.session_state.bundle = store.bundle(selected['id'])
    if any(r['status'] == 'failed' for r in runs):
        with st.expander('Falhas registradas'):
            st.dataframe([{'execução': r['id'][:8], 'erro': r['error']} for r in runs if r['status'] == 'failed'])
    st.divider()
    uploaded = st.file_uploader('Importar cenário · JSON ou ZIP', type=['json', 'zip'])
    if st.button('Aplicar arquivo', disabled=uploaded is None, use_container_width=True):
        try:
            raw = import_scenario(uploaded.getvalue())
        except ValueError as exc:
            st.error(str(exc))
        else:
            load(raw.model_dump())
    st.caption('Mensal · até 6 células · até 36 meses')
    st.caption('Execução local • Sem credenciais • v1.0.0')

st.markdown('''<header class="masthead"><div><div class="eyebrow">SISTEMA DE PLANEJAMENTO · MANUFATURA</div>
<h1>Fábrica em Fluxo</h1><p>Planeje recursos, acompanhe restrições e compare decisões ao longo do tempo.</p></div>
<div class="masthead-meta">AMBIENTE<span>LOCAL · DADOS SINTÉTICOS</span>ESCOPO<span>ATÉ 6 CÉLULAS / 36 MESES</span></div></header>''', unsafe_allow_html=True)
section = st.radio('Navegação principal', ['01 · Cenário', '02 · Produção', '03 · Comparar', '04 · Modelo'],
                   horizontal=True, label_visibility='collapsed', key='active_view')
st.caption('SIMULAÇÃO EDUCATIVA · Hipóteses explícitas · Sem validação industrial')

if section == '01 · Cenário':
    # Widget input data must remain stable while editing. Changing data_editor's
    # base after saving resets its widget identity and can discard the next edit.
    current = Scenario.model_validate(st.session_state.editor_source)
    version = st.session_state.editor_version
    st.subheader('Um cenário, decisões que você controla')
    st.caption('Altere os campos e salve uma revisão. Resultados já executados permanecem vinculados à revisão original.')
    with st.form(f'editor_{version}'):
        name = st.text_input('Nome do cenário', current.name)
        description = st.text_area('Pergunta do experimento', current.description, height=80,
                                   placeholder='Como um segundo turno afeta entregas, custos e estoque?')
        a, b, c, d = st.columns(4)
        start = a.text_input('Mês inicial · AAAA-MM', current.start)
        months = b.number_input('Duração · meses', 1, 36, current.months)
        seed = c.number_input('Semente dos choques', 0, 2**32-1, current.seed)
        budget = d.number_input('Orçamento inicial · R$', 0., 1e12, current.budget)
        a, b, c = st.columns(3)
        policy_mode = a.selectbox('Modo de decisão', list(MODE), index=list(MODE).index(current.policy_mode), format_func=MODE.get)
        demand_mode = b.selectbox('Pedidos não atendidos', ['backlog', 'lost'],
            index=['backlog', 'lost'].index(current.demand_mode), format_func=lambda v: {'backlog': 'Acumular atrasos', 'lost': 'Registrar demanda perdida'}[v])
        enabled = c.checkbox('Ativar choques reproduzíveis', current.shocks)
        st.markdown('#### Decisões por célula')
        st.caption('Equipe é o número de pessoas em cada turno; mais turnos exigem mais pessoas e salários. Investimento entra no mês seguinte.')
        policies = st.data_editor([{'line': k, **p.model_dump()} for k, p in current.policy.items()],
            column_config=POLICY_CONFIG, hide_index=True, use_container_width=True, key=f'policy_{version}')
        st.markdown('#### Estrutura, pedidos e custos')
        lines = []
        for line in current.lines:
            raw = line.model_dump()
            with st.expander(line.name+' · parâmetros da célula'):
                raw['name'] = st.text_input('Nome da célula', line.name, key=f'name_{line.id}_{version}')
                fields = [
                    ('capacity', 'Capacidade por turno · un./mês', .001, 1e6),
                    ('productivity', 'Produtividade · un./pessoa/mês', .001, 1e5),
                    ('availability', 'Disponibilidade base · 0 a 1', 0., 1.),
                    ('defect_rate', 'Taxa base de refugo · 0 a 0,5', 0., .5),
                    ('material_per_unit', 'Material por unidade iniciada', .001, 10000.),
                    ('initial_materials', 'Estoque inicial de materiais', 0., 1e8),
                    ('initial_stock', 'Estoque inicial acabado', 0, 1000000),
                    ('initial_backlog', 'Pedidos iniciais em atraso', 0, 1000000),
                ]
                columns = st.columns(4)
                for i, (key, label, low, high) in enumerate(fields):
                    raw[key] = columns[i%4].number_input(label, low, high, getattr(line, key), key=f'{line.id}_{key}_{version}')
                demand_text = st.text_input('Pedidos novos · valor recorrente ou lista mensal separada por vírgulas',
                    ', '.join(map(str, line.demand)), key=f'demand_{line.id}_{version}')
                raw['demand_text'] = demand_text
                columns = st.columns(3)
                cost_fields = [('material_cost', 'Material · R$/un.', 1e6), ('wage', 'Salário · R$/pessoa/turno', 1e6),
                    ('fixed_cost', 'Custo fixo · R$/mês', 1e8), ('variable_cost', 'Processamento · R$/un. bruta', 1e6),
                    ('maintenance_cost', 'Manutenção máxima · R$/mês', 1e7),
                    ('investment_cost', 'Investimento · R$/capacidade adicional', 1e6),
                    ('holding_cost', 'Armazenagem · R$/un. acabada/mês', 1e6), ('sale_price', 'Recebimento por entrega · R$/un.', 1e7)]
                for i, (key, label, high) in enumerate(cost_fields):
                    raw[key] = columns[i%3].number_input(label, 0., high, getattr(line, key), key=f'{line.id}_{key}_{version}')
            lines.append(raw)
        with st.expander('Sequência manual por período'):
            st.caption('No modo manual, preencha todas as células em todos os meses. Após mudar a duração, salve no modo fixo e use “Atualizar formulário do cenário salvo” para regenerar a grade, ou importe um cenário JSON completo.')
            manual_rows = []
            for month in range(current.months):
                period_policy = current.manual[month] if month < len(current.manual) else current.policy
                manual_rows.extend({'month': month+1, 'line': k, **p.model_dump()} for k, p in period_policy.items())
            manual_table = st.data_editor(manual_rows, column_config=POLICY_CONFIG, hide_index=True,
                use_container_width=True, key=f'manual_{version}')
        with st.expander('Metas e pesos da busca local', expanded=current.policy_mode == 'endogenous'):
            st.caption('Proporções usam 0 a 1. Pesos maiores dão mais importância; a escala normaliza o desvio. A busca avalia alternativas locais e não garante ótimo global.')
            goals = st.data_editor([g.model_dump() for g in current.goals], num_rows='dynamic', hide_index=True,
                column_config={
                    'indicator': st.column_config.SelectboxColumn('Indicador', options=['service','backlog','stock','unit_cost','budget','scrap_rate','utilization'], required=True),
                    'kind': st.column_config.SelectboxColumn('Tipo: alvo / teto / piso', options=['target','upper','lower'], required=True),
                    'target': st.column_config.NumberColumn('Alvo ou limite', required=True),
                    'weight': st.column_config.NumberColumn('Peso', min_value=0., max_value=100., required=True),
                    'scale': st.column_config.NumberColumn('Escala do desvio', min_value=.000001, required=True)}, key=f'goals_{version}')
        st.info('O orçamento é um saldo projetado. Um saldo negativo indica necessidade de recursos; não bloqueia automaticamente a operação.')
        left, right = st.columns(2)
        save = left.form_submit_button('Salvar cenário', use_container_width=True)
        run = right.form_submit_button('Salvar e simular', type='primary', use_container_width=True)
    if save or run:
        try:
            for line in lines:
                line['demand'] = [int(v.strip()) for v in line.pop('demand_text').split(',')]
            manual = [{r['line']: {k: v for k, v in r.items() if k not in ('line', 'month')}
                       for r in manual_table if r['month'] == m+1} for m in range(months)] if policy_mode == 'manual' else []
            raw = current.model_dump() | dict(name=name, description=description, start=start, months=months,
                seed=seed, budget=budget, policy_mode=policy_mode, demand_mode=demand_mode, shocks=enabled,
                lines=lines, goals=goals, manual=manual,
                policy={p['line']: {k: v for k, v in p.items() if k != 'line'} for p in policies})
            validated = Scenario.model_validate(raw)
            revision = store.save(validated, parent=st.session_state.revision or st.session_state.parent)
            st.session_state.scenario = validated.model_dump()
            st.session_state.revision = revision
            st.success('Cenário salvo · revisão '+revision[:8])
            if run:
                with st.spinner('Calculando períodos e conferindo balanços...'):
                    st.session_state.bundle = execute(store, revision)
                st.success('Simulação concluída. Consulte Produção para analisar os resultados.')
        except (ValueError, TypeError) as exc:
            st.error('Revise os campos: '+str(exc))
    if st.session_state.revision:
        st.caption('Revisão salva atual: '+st.session_state.revision[:8]+'. Alterações no formulário só são aplicadas ao salvar.')
        st.button('Atualizar formulário do cenário salvo', on_click=set_scenario,
                  kwargs={'raw': copy.deepcopy(st.session_state.scenario),
                          'revision': st.session_state.revision, 'parent': st.session_state.parent})
        if st.button('Simular cenário salvo'):
            with st.spinner('Executando cenário salvo...'):
                st.session_state.bundle = execute(store, st.session_state.revision)
        st.download_button('Baixar cenário · JSON', json.dumps(st.session_state.scenario, ensure_ascii=False, indent=2),
                           'cenario.json', 'application/json')
    with st.expander('Adicionar ou remover células · editor avançado'):
        advanced = st.text_area('Cenário completo em JSON', json.dumps(st.session_state.scenario, ensure_ascii=False, indent=2),
                                height=240, key=f'advanced_{version}')
        if st.button('Validar e carregar JSON'):
            try:
                parsed = Scenario.model_validate_json(advanced)
            except ValueError as exc:
                st.error(str(exc))
            else:
                load(parsed.model_dump(), parent=st.session_state.revision or st.session_state.parent)


def chart(rows, keys, title):
    figure = go.Figure()
    colors = ['#e66b3d', '#187f74', '#c29a32', '#38463d']
    for key, color in zip(keys, colors):
        figure.add_trace(go.Scatter(x=[r['period'] for r in rows], y=[r[key] for r in rows],
            mode='lines+markers', name=LABELS.get(key, key), line=dict(color=color, width=3)))
    figure.update_layout(title=title, height=320, margin=dict(l=20, r=15, t=50, b=20),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation='h', y=-.2),
        xaxis=dict(type='category'), yaxis=dict(gridcolor='#e7eaf4'))
    st.plotly_chart(figure, use_container_width=True)


if section == '02 · Produção':
    if 'bundle' not in st.session_state:
        st.info('Simule um cenário ou abra uma execução salva no painel lateral.')
    else:
        bundle = st.session_state.bundle
        rows = bundle['result']['rows']
        last = rows[-1]
        st.subheader(bundle['scenario']['name'])
        st.caption(f"Execução {bundle['run_id'][:8]} · revisão {bundle['revision'][:8]} · {MODE[bundle['scenario']['policy_mode']]} · {len(rows)} meses · dados sintéticos")
        variant = copy.deepcopy(bundle['scenario'])
        variant['name'] = variant['name'][:100]+' · variação'
        st.button('Criar variação deste resultado', on_click=set_scenario,
                  kwargs={'raw': variant, 'parent': bundle['revision']})
        a, b, c, d = st.columns(4)
        a.metric('Produção boa · total', f"{sum(r['good'] for r in rows):,}".replace(',', '.'))
        total_demand = sum(r['demand'] for r in rows)
        b.metric('Serviço · pedidos novos', format_value(sum(r['shipped_current'] for r in rows)/total_demand if total_demand else None, True))
        c.metric('Backlog · final', str(last['backlog']))
        d.metric('Orçamento final · R$', format_value(last['budget']))
        if any(r['funding_gap'] for r in rows):
            st.warning('Há meses com déficit de orçamento. O modelo mantém a operação e registra a necessidade de recursos; não representa uma operação financeiramente viável por si só.')
        a, b = st.columns(2)
        with a:
            chart(rows, ['planned', 'gross', 'good'], 'Do plano à produção boa')
        with b:
            chart(rows, ['demand', 'shipped', 'backlog'], 'Pedidos, entregas e atrasos')
        st.markdown('#### Abra um período e acompanhe o cálculo')
        period = st.select_slider('Período', options=list(range(len(rows))), value=len(rows)-1,
                                  format_func=lambda i: rows[i]['period'])
        row = rows[period]
        st.dataframe([{'Indicador': label, 'Valor': format_value(row[key], key in PERCENT)}
                      for key, label in LABELS.items()], hide_index=True, use_container_width=True)
        st.markdown('**Restrições por célula**')
        st.dataframe([{'Célula': t['name'], 'Planejado': t['planned'], 'Limite equipamento': t['equipment_limit'],
            'Limite equipe': t['labor_limit'], 'Limite materiais': t['material_limit'],
            'Produção bruta': t['gross'], 'Produção boa': t['good'], 'Refugo': t['scrap'],
            'Restrição ativa': ', '.join(t['constraints'])} for t in row['traces']], hide_index=True, use_container_width=True)
        for trace in row['traces']:
            with st.expander(trace['name']+' · rastro de recursos, atendimento e custos'):
                st.write(f"Materiais: {trace['opening']['materials']:.2f} + {trace['delivered']:.2f} recebidos − {trace['consumed']:.2f} consumidos = {trace['closing']['materials']:.2f}.")
                st.write(f"Acabados: {trace['opening']['stock']} iniciais + {trace['good']} bons − {trace['shipped']} entregues = {trace['stock']}.")
                st.write(f"Pedidos: {trace['opening']['backlog']} atrasados + {trace['demand']} novos = {trace['shipped']} entregues + {trace['backlog']} em atraso + {trace['lost']} perdidos.")
                st.json(trace)
        st.markdown('**Por que essa decisão?**')
        st.write(row['decision']['reason'])
        st.dataframe(row['goal_terms'], hide_index=True, use_container_width=True)
        with st.expander('Decisão e alternativas avaliadas'):
            st.json(row['decision'])
        with st.expander('Trajetória completa e rastreabilidade'):
            st.dataframe([{k: v for k, v in r.items() if not isinstance(v, (list, dict))} for r in rows], hide_index=True)
            st.json({'hashes': bundle['hashes'], 'environment': bundle['environment']})
        a, b = st.columns(2)
        a.download_button('Baixar indicadores · CSV', csv_bytes(rows), 'indicadores.csv', 'text/csv', use_container_width=True)
        b.download_button('Baixar execução completa · ZIP', export_package(bundle), 'fabrica-em-fluxo.zip', 'application/zip', use_container_width=True)

if section == '03 · Comparar':
    available = [r for r in store.runs() if r['status'] == 'complete']
    if len(available) < 2:
        st.info('Execute pelo menos dois cenários. Use “Criar variação deste resultado” para alterar uma decisão e comparar.')
    else:
        label = lambda r: json.loads(r['scenario'])['name']+' · '+r['id'][:8]
        left, right = st.columns(2)
        a_id = left.selectbox('Execução A', available, format_func=label)
        b_options = [r for r in available if r['id'] != a_id['id']]
        b_id = right.selectbox('Execução B', b_options, format_func=label)
        a, b = store.bundle(a_id['id']), store.bundle(b_id['id'])
        diff, warnings = comparison(a, b)
        if warnings:
            st.warning('Comparação com condições diferentes: '+', '.join(warnings)+'. Verifique as hipóteses antes de atribuir diferenças às decisões.')
        else:
            st.success('Mesmas condições iniciais e mesmo caminho de choques; diferenças de decisão e metas estão abaixo.')
        with st.expander('O que mudou entre os cenários?', expanded=True):
            st.json(diff)
        st.caption('A tabela compara o último mês de cada execução; horizontes diferentes não têm a mesma data final.')
        st.dataframe([{'Indicador': label, 'A': format_value(a['result']['rows'][-1][key], key in PERCENT),
                      'B': format_value(b['result']['rows'][-1][key], key in PERCENT)} for key, label in LABELS.items()], hide_index=True)
        metric = st.selectbox('Trajetória a comparar', list(LABELS), format_func=LABELS.get)
        fig = go.Figure()
        for title, experiment, color in [('A', a, '#e66b3d'), ('B', b, '#187f74')]:
            fig.add_trace(go.Scatter(x=[r['period'] for r in experiment['result']['rows']],
                y=[r[metric] for r in experiment['result']['rows']], name=title, mode='lines+markers', line_color=color))
        fig.update_layout(xaxis_type='category', yaxis_title=LABELS[metric], height=360)
        st.plotly_chart(fig, use_container_width=True)

if section == '04 · Modelo':
    st.markdown((ROOT/'docs/modelo.md').read_text(encoding='utf-8') if (ROOT/'docs/modelo.md').exists() else 'Documentação em preparação.')
store.close()
