# Inspeção prévia e decisões de arquitetura

A especificação `../projeto_fabrica_em_fluxo.md` foi lida antes das alterações. Foram inspecionados o README,
dependências, interface, schema, persistência, orquestração, motor Python/C++ e testes do BASE.
Os arquivos originais não são importados pela variante. `original-hashes.json` registra os hashes anteriores dos arquivos de projeto,
excluindo runtime, build e caches. `sources/` permanece somente leitura.

| Parte existente | Avaliação | Decisão na variante |
|---|---|---|
| Streamlit + pandas + Plotly | Infraestrutura genérica para formulários, tabelas, gráficos e downloads | Mesmas bibliotecas e padrão de app independente |
| Pydantic com campos limitados e `extra=forbid` | Validação reutilizável como padrão | Novo schema estritamente de manufatura |
| SQLite, UUIDs, revisões e execuções | Padrão genérico de persistência | Banco próprio com revisão imutável, relação de variação e estados de execução |
| JSON canônico, SHA-256, CSV e ZIP | Padrão genérico de auditabilidade | Reimplementação pequena com definições industriais e exportação validada |
| Motor C++ e estruturas de agentes econômicos | Acoplados a regras, balanços e entidades econômicas | Novo motor puro Python; nenhuma mudança de rótulos do modelo original |
| Nelder-Mead e projeções C++ | Avaliador e variáveis acoplados ao motor; simplex contínuo inadequado para equipe/turnos inteiros | Reaproveitar ideia de comparar com baseline e metas normalizadas; busca discreta explicável |
| LangGraph e assistente de IA | Orquestração de conversa/pesquisa desnecessária ao fluxo local | Serviço Python simples de validar, executar, conferir e persistir |
| Integrações de dados oficiais | Não pertinentes ao modelo sintético de manufatura | Não incluídas |

O motor Python facilita inspeção em sala de aula e elimina a necessidade de compilador; o escopo máximo é pequeno
(36 meses, 6 células e 73 avaliações locais/mês). Não há dependência do diretório irmão, API ou credencial em execução.
O ambiente virtual já instalado no workspace é apenas uma conveniência; uma instalação local própria é documentada.

## Fronteiras

- `fluxo/schema.py`: tipos, intervalos, domínios, integridade de políticas e horizontes.
- `fluxo/engine.py`: transformação pura do cenário em trajetória; sem banco, rede, interface ou arquivos.
- `fluxo/storage.py`: armazenamento transacional de revisões e execuções em `runtime/fluxo.sqlite`.
- `fluxo/service.py`: orquestração, invariantes, hashes e comparação.
- `fluxo/export.py`: importação de cenários e exportação JSON/CSV/ZIP. Não extrai arquivos ZIP no disco.
- `app/main.py`: formulários e visualização; não implementa as equações do motor.
- `cli.py`: execução independente da interface.

## Escolhas pequenas resolvidas

Período mensal; dois produtos agregados sintéticos na demonstração; três turnos no máximo; até 200 pessoas por turno;
entrega de material no próprio mês; capacidade investida no próximo mês; manutenção sem efeito cumulativo;
atendimento de atrasos antes de pedidos novos; backlog ou perda, sem cancelamento por idade;
preços constantes; custos em reais nominais; saldo negativo explicitamente reportado sem bloqueio automático.
As razões são armazenadas como frações. Não há indicador composto OEE.

O limite de produção planejada é 1 milhão de unidades por célula/mês. Parâmetros positivos têm limites finitos;
NaN, infinito, campos desconhecidos, IDs duplicados e políticas incompletas são recusados.
A grade manual usa o horizonte carregado; para mudar sua duração, salvar primeiro em modo fixo, atualizar o formulário do cenário salvo e depois editar a grade,
ou importar JSON com a sequência completa. Até seis células podem ser definidas no editor JSON avançado.

Revisões são imutáveis, exceto o estado de uma execução que passa de `running` a `complete` ou `failed`.
Uma interrupção externa de processo pode deixar `running`; isso não é apresentado como resultado concluído.
O banco é local e não oferece autenticação ou colaboração multiusuário. O servidor escuta somente em loopback.
