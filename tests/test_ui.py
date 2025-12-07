from streamlit.testing.v1 import AppTest
from fluxo.storage import ROOT, Store


def button(app, label):
    return next(b for b in app.button if b.label == label)


def navigate(app, option):
    next(r for r in app.radio if r.label == 'Navegação principal').set_value(option).run()


def test_edit_run_vary_compare_and_resume(tmp_path, monkeypatch):
    monkeypatch.setenv('FLUXO_HOME', str(tmp_path/'ui'))
    app = AppTest.from_file(str(ROOT/'app/main.py'), default_timeout=45).run()
    assert not app.exception
    next(x for x in app.text_input if x.label == 'Nome do cenário').set_value('Experimento verificado')
    button(app, 'Salvar e simular').click().run()
    assert not app.exception
    first = app.session_state['bundle']
    assert first['scenario']['name'] == 'Experimento verificado'
    navigate(app, '02 · Produção')
    assert len(app.metric) == 4
    button(app, 'Criar variação deste resultado').click().run()
    assert not app.exception
    assert app.session_state['parent'] == first['revision']
    navigate(app, '01 · Cenário')
    next(x for x in app.selectbox if x.label == 'Modo de decisão').select('endogenous')
    button(app, 'Salvar e simular').click().run()
    assert not app.exception
    second = app.session_state['bundle']
    assert second['scenario']['policy_mode'] == 'endogenous'
    assert first['run_id'] != second['run_id']
    navigate(app, '03 · Comparar')
    assert any(x.label == 'Execução A' for x in app.selectbox)
    reopened = AppTest.from_file(str(ROOT/'app/main.py'), default_timeout=45).run()
    button(reopened, 'Abrir resultado').click().run()
    assert not reopened.exception
    navigate(reopened, '02 · Produção')
    assert reopened.session_state['bundle']['run_id'] == second['run_id']
    button(reopened, 'Retomar cenário').click().run()
    assert reopened.session_state['revision'] == second['revision']
    store = Store(tmp_path/'ui')
    assert len(store.runs()) == 2
    store.close()


def test_invalid_form_does_not_execute(tmp_path, monkeypatch):
    monkeypatch.setenv('FLUXO_HOME', str(tmp_path/'invalid'))
    app = AppTest.from_file(str(ROOT/'app/main.py')).run()
    next(x for x in app.text_input if x.label == 'Mês inicial · AAAA-MM').set_value('2026-15')
    button(app, 'Salvar e simular').click().run()
    assert not app.exception and app.error
    store = Store(tmp_path/'invalid')
    assert not store.runs() and not store.revisions()
    store.close()


def test_policy_and_manual_grid_edits_reach_engine(tmp_path, monkeypatch):
    monkeypatch.setenv('FLUXO_HOME', str(tmp_path/'grid'))
    app = AppTest.from_file(str(ROOT/'app/main.py'), default_timeout=45).run()
    app.session_state['policy_0'] = {'edited_rows': {0: {'workers': 0}}, 'added_rows': [], 'deleted_rows': []}
    button(app, 'Salvar e simular').click().run()
    assert not app.exception
    assert app.session_state['bundle']['result']['rows'][0]['traces'][0]['gross'] == 0
    next(x for x in app.selectbox if x.label == 'Modo de decisão').select('manual')
    app.session_state['manual_0'] = {'edited_rows': {0: {'workers': 2}}, 'added_rows': [], 'deleted_rows': []}
    button(app, 'Salvar e simular').click().run()
    assert not app.exception
    manual = app.session_state['bundle']
    assert manual['scenario']['manual'][0]['alpha']['workers'] == 2
    assert manual['result']['rows'][0]['traces'][0]['gross'] == 200
