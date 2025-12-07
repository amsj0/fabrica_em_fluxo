# Fábrica em Fluxo

Simulador educativo de **planejamento agregado mensal de manufatura**.
Execução independente, offline e sem credenciais. Dados de demonstração sintéticos; não é previsão industrial validada.

## Abrir neste computador

Execute `iniciar.cmd` nesta pasta. Endereço: **http://127.0.0.1:8502**.
O lançador usa `.venv` local ou o ambiente compartilhado `../.venv`. Porta independente da aplicação original.

## Instalar em outro computador

Requer Python 3.12. Copie somente esta pasta; não é necessário o projeto original nem compilador C++.
Na pasta `fabrica_em_fluxo/`, execute no Windows:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m streamlit run app/main.py
```

Linux/macOS: use `python3 -m venv .venv` e `.venv/bin/python` nos comandos. Essas plataformas não foram testadas nesta entrega.
Instalação inicial requer acesso aos pacotes; depois disso, o fluxo principal funciona offline.
As dependências diretas estão fixadas em `requirements.txt`; não se pressupõe que versões transitivas de uma nova instalação sejam idênticas.

## Fluxo de uso

1. Carregue uma demonstração ou configure nome, horizonte, recursos, pedidos e custos.
2. Escolha política fixa, manual por mês ou busca local por metas. Use pesos e escalas explícitos.
3. Clique **Salvar e simular**. Campos inválidos impedem persistência e execução.
4. Em **Resultados e rastros**, examine as trajetórias, selecione um mês e confira restrições, balanços, decisões e metas.
5. Clique **Criar variação deste resultado**, altere uma decisão e execute novamente.
6. Em **Comparar**, selecione duas execuções e revise as diferenças de hipóteses junto com indicadores e trajetórias.
7. Baixe CSV ou ZIP. O pacote contém cenário, execução, indicadores, políticas, linhas, hashes e documentação.

Cenários e execuções são retomados pela barra lateral. Importação aceita cenário JSON ou ZIP exportado.
Configuração avançada permite adicionar/remover células (1 a 6). Ao mudar a duração de uma sequência manual,
salve primeiro no modo fixo e clique **Atualizar formulário do cenário salvo** para atualizar a grade, ou importe o JSON completo.

## Comandos de execução e teste

Com o ambiente deste workspace, a partir desta pasta:

```powershell
../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=runtime/test-local
../.venv/Scripts/python.exe cli.py --scenario data/demo/01_base.json --export runtime/base.zip
../.venv/Scripts/python.exe cli.py --scenario data/demo/03_busca_local.json --export runtime/busca.zip
../.venv/Scripts/python.exe -m streamlit run app/main.py --server.address=127.0.0.1 --server.port=8502 --server.headless=true
```

Em uma instalação independente, substitua `../.venv` por `.venv`. Para ambiente temporário isolado:
defina `FLUXO_HOME` ou use `cli.py --home caminho`. Faça backup de `runtime/fluxo.sqlite` para preservar cenários e execuções.
Cada execução concluída inclui o JSON do cenário exato, UUID, versão, hashes de fontes e hash do resultado.
Os hashes auditam integridade; não são assinatura digital ou validação científica.

## Demonstrações

- `01_base.json`: duas células, política fixa e nenhum choque.
- `02_manual.json`: segundo turno e mais equipe/material a partir do terceiro mês.
- `03_busca_local.json`: metas ponderadas e choques reproduzíveis.
- `04_materiais_escassos.json`: escassez de matéria-prima, backlog e déficit de orçamento.
- `05_demanda_perdida.json`: pedidos não atendidos são perdidos, sem backlog.

Leia [as equações e hipóteses](docs/modelo.md), [a arquitetura e inspeção inicial](docs/arquitetura.md)
e [o registro de validação](docs/validacao.md). **Orçamento negativo indica necessidade de recursos, sem bloquear a operação.**
A busca compara alternativas locais; não garante ótimo global. Não há simulação detalhada de chão de fábrica.
