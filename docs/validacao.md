# Registro de validação — 07/12/2025

## Resultados

- **37 testes Python da variante aprovados**, incluindo 3 testes de interface Streamlit.
- **20 testes Python do BASE aprovados**, sem alteração dos testes originais.
- Os dois executáveis C++ originais passaram: `engine_tests.exe` (8 grupos) e `government_tests.exe`.
- **42 arquivos de projeto originais** conferidos por SHA-256: **0 modificados**. Runtime, build e caches não fazem parte desse manifesto.
- Cinco demonstrações sintéticas executadas e exportadas. Importação de cenário e consistência numérica dos CSV/JSON/ZIP testadas.
- Servidor local iniciado em **http://127.0.0.1:8502** e interface real inspecionada no navegador.
- Execução da base acionada pelo botão “Salvar e simular”, concluída e exibida com gráficos, indicadores e rastros.
  Base: 9.168 unidades boas em 6 meses, 62 pedidos em backlog final e R$ 252.087,00 de saldo final.
  Esses números são resultados das hipóteses sintéticas, não observações industriais.
- Evidência visual: `resultados-verificados.png`. Evidência de demonstrações e hashes: `execution-evidence.json`.

## Cobertura das regras

Testes exercitam limites de equipamento, equipe e materiais; produção zero; manutenção e refugo;
consumo de materiais em unidades rejeitadas; conservação de acabados; prioridade de backlog;
demanda perdida; razões com denominador zero; custos e caixa; investimento disponível no mês seguinte;
choques comuns independentes das decisões; reprodução por semente; ausência de mutação de entradas;
equivalência operacional entre sequência manual constante e política fixa; metas, empates e baseline da busca;
domínios e integridade de cenários; persistência entre processos; revisões pai/filha; falhas registradas;
exportações consistentes e rejeição de arquivos inválidos; diferenças nas comparações.

Os testes de interface cobrem edição e execução, criação de variação, modo endógeno, comparação, nova sessão,
retomada de cenário, formulário inválido e edições reais do estado das grades fixa e manual.
Foi corrigido um problema encontrado no teste adicional: a base de dados de um editor de grade não pode mudar após
salvar sem recarregar o formulário. O formulário agora preserva sua base durante a edição e possui ação explícita para recarregar a revisão salva.

## Comandos executados

A partir de `fabrica_em_fluxo/`, utilizando o ambiente Python já instalado no workspace:

```powershell
$env:TEMP=(Resolve-Path runtime).Path
$env:TMP=$env:TEMP
../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=runtime/test-corrected
# 37 passed in 7.01s

../.venv/Scripts/python.exe cli.py --scenario data/demo/01_base.json --export runtime/base.zip

../.venv/Scripts/python.exe -m streamlit run app/main.py --server.address=127.0.0.1 --server.port=8502 --server.headless=true --browser.gatherUsageStats=false
```

A partir de `base/`, com temporários redirecionados para a variante e bytecode desabilitado:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEMP=(Resolve-Path ../fabrica_em_fluxo/runtime).Path
$env:TMP=$env:TEMP
../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=../fabrica_em_fluxo/runtime/base-regression
# 20 passed, 1 warning in 9.42s
```

A partir da raiz do workspace:

```powershell
./base/build/engine_tests.exe
./base/build/government_tests.exe ./base/data/demo/base.json
```

Os binários originais foram executados diretamente para evitar regravar os logs de CTest em seu diretório.
O servidor foi iniciado como processo oculto com `Start-Process -WindowStyle Hidden`; logs em `runtime/server*.log`.

## Limitações e avisos do ambiente

- A tentativa inicial de servidor no sandbox não ficou acessível. O processo local foi iniciado com a permissão de execução
  necessária, mantendo bind somente em `127.0.0.1`. A interface foi então verificada com sucesso.
- O teste original emite um aviso de depreciação do LangGraph; a variante não usa essa dependência.
- Streamlit 1.50 emite aviso sobre o parâmetro `use_container_width`, ainda funcional nessa versão fixada.
- A primeira rodada com diretório temporário padrão mostrou erro de limpeza de temporários do ambiente; as rodadas finais
  redirecionaram TEMP/TMP para `runtime` e concluíram sem esse erro.
- Não foi feita instalação limpa por download de dependências nem execução em Linux/macOS. O ambiente existente foi reutilizado.
- Não foram feitos estudo com usuários, calibração ou validação científica/industrial. Todos os testes de software planejados foram executados.
