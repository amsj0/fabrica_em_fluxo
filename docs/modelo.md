# Como interpretar a Fábrica em Fluxo

Este é um **simulador educativo de planejamento agregado mensal**, versão 1.0.0.
Todos os exemplos são **sintéticos**. Não há calibração, dados industriais oficiais ou validação industrial.
Testes de software verificam as regras implementadas, não a validade das hipóteses no mundo real.

## Unidade de análise

Cada célula fabrica um produto agregado. As unidades das células são tratadas como equivalentes para somar indicadores;
para produtos de portes diferentes, examine os rastros individuais. Materiais, pessoal, capacidade e produtos acabados
pertencem a uma célula: não há transferência ou competição por um recurso compartilhado. Somente o orçamento é comum.
Não existem máquinas individuais, roteiros, ordens individuais, filas intramensais ou sequenciamento de operações.

O mês inicial é o primeiro período de decisões; saldos anteriores estão em `initial` e no campo `opening` dos rastros.
Pedidos podem ser constantes (lista com um valor) ou uma lista com exatamente um valor por mês.
Quantidades produzidas e pedidos são inteiros; materiais e dinheiro usam ponto flutuante sem arredondamento intermediário.
O arredondamento na tela é apenas de apresentação. `floor(x)` significa arredondar para baixo.

## Sequência mensal

1. **Pedidos e recursos.** Calcular pedidos novos = floor(pedido informado × fator de demanda). Receber a reposição
   de materiais do mês × fator de entrega. Não há prazo de fornecimento: recebimento ocorre no início do próprio mês.
   A parte não entregue é cancelada, não é cobrada nem passa ao próximo mês.
2. **Disponibilidade e manutenção.** Capacidade nominal = capacidade por turno × turnos. Disponibilidade efetiva =
   clip(disponibilidade base + 0,08 × manutenção − parada aleatória, 0, 1) × (1 − 0,15 × manutenção).
   Assim, manutenção exige uma parada planejada, pode recuperar disponibilidade e reduz o refugo.
   Seu efeito não acumula de mês para mês; não há envelhecimento de equipamentos.
3. **Limites físicos.** Limite de equipamento = floor(capacidade nominal × disponibilidade efetiva).
   Limite de equipe = floor(pessoas por turno × turnos × produtividade mensal por pessoa).
   Limite de materiais = floor((materiais iniciais + recebidos) / material por unidade).
   Produção bruta realizada = mínimo entre plano bruto e os três limites. O rastro identifica todas as restrições empatadas.
   O plano é um teto de produção, independentemente dos pedidos; a política pode produzir para estoque.
4. **Qualidade.** Taxa parametrizada de refugo = min(0,5; taxa base × (1 − 0,5 × manutenção) + 0,05 × parada aleatória).
   Refugo = floor(produção bruta × taxa parametrizada); produção boa = bruta − refugo.
   Todas as unidades iniciadas, inclusive refugo, consomem material e custo de processamento. Não há retrabalho ou recuperação.
5. **Atendimento.** Disponível para entrega = estoque acabado inicial + produção boa.
   Entregas = mínimo(disponível, backlog inicial + pedidos novos). Pedidos atrasados têm prioridade.
   O restante vira backlog ou demanda perdida, conforme a opção global do cenário. Demanda perdida exige backlog inicial zero.
6. **Saldos e custos.** Atualizar materiais e acabados, custos e orçamento. Investimento decidido agora adiciona capacidade
   **apenas no mês seguinte**. A quantidade investida é capacidade adicional por turno, não um valor em reais.

## Indicadores e fórmulas

| Indicador | Definição |
|---|---|
| Produção planejada | Soma dos planos brutos configurados, antes dos limites e do refugo |
| Produção realizada (bruta) | Soma das unidades efetivamente iniciadas |
| Produção boa | Produção bruta − refugo |
| Utilização | Produção bruta / limite de equipamento já descontadas as paradas |
| Disponibilidade | Tempo produtivo equivalente / tempo nominal; na fábrica, média ponderada pela capacidade nominal |
| Qualidade | Produção boa / produção bruta |
| Refugo observado | Quantidade de refugo / produção bruta; pode diferir da taxa parametrizada pelo arredondamento |
| Nível de serviço | Pedidos **novos** entregues no próprio mês / pedidos novos; entregas de backlog não entram no numerador |
| Atendimento total (`fulfillment`) | Todas as entregas / (pedidos novos + backlog inicial) |
| Backlog | Backlog anterior + pedidos novos − entregas, no modo acumular atrasos |
| Demanda perdida | Pedidos não atendidos no mês, no modo demanda perdida; não acumulam |
| Estoque acabado | Estoque anterior + produção boa − entregas |
| Materiais finais | Materiais anteriores + recebidos − produção bruta × material por unidade |
| Custo unitário | Custo operacional do mês / produção boa do mês |
| Saldo do orçamento | Saldo anterior + recebimentos pelas entregas − saídas de caixa |
| Necessidade de recursos | max(0, −saldo do orçamento) |

Proporções são armazenadas de 0 a 1 e mostradas como porcentagens na tabela de indicadores.
Denominador zero gera `null` no JSON, célula vazia no CSV e “—” na tela; não significa zero nem 100%.
As razões agregadas dividem somas, em vez de tirar uma média simples das porcentagens das células.
O serviço total exibido no cartão divide a soma das entregas de pedidos novos pela soma dos pedidos novos de todos os meses.
Não se calcula OEE nesta versão: utilização, disponibilidade e qualidade são indicadores separados.

## Custos e orçamento

- Salários = pessoas por turno × turnos × salário mensal por pessoa. Cada turno possui uma equipe distinta, sem horas extras.
- Manutenção = intensidade de manutenção × custo máximo de manutenção.
- Processamento = produção bruta × custo variável por unidade.
- Materiais consumidos = consumo físico × custo por unidade de material.
- Armazenagem = estoque acabado final × custo de armazenagem. Materiais em estoque não têm custo de armazenagem nesta versão.
- Custo operacional = salários + manutenção + custo fixo + processamento + materiais consumidos + armazenagem.
- Compras de materiais = quantidade realmente recebida × preço de material.
- Investimento = capacidade adicional × custo por unidade de capacidade.
- Saída de caixa = custo operacional − materiais consumidos em reais + compras de materiais + investimento.
- Recebimentos = entregas × preço de venda. O pagamento é imediato e o refugo não gera receita.

Materiais iniciais são considerados já pagos antes do horizonte. O custo de seu consumo entra no custo unitário,
mas não é cobrado novamente no caixa. Investimento sai do caixa sem entrar no custo operacional; não há depreciação.
Custos fixos, salários da equipe configurada e manutenção são cobrados mesmo que a produção seja zero.

**O orçamento é um saldo projetado, não uma restrição automática.** Saldo negativo representa necessidade de financiamento
e gera aviso. O modelo continua a operação para tornar visível o déficit; não concede crédito nem demonstra viabilidade financeira.

## Choques e reprodutibilidade

Com choques desligados, fatores de demanda e entrega são 1 e paradas aleatórias são 0.
Com choques ligados: demanda ~ Uniforme(0,85; 1,15), parada ~ Uniforme(0; 0,12), entrega ~ Uniforme(0,8; 1).
As três amostras são geradas nessa ordem por um gerador local inicializado por SHA-256 de `semente:mês:id_da_célula`.
Não dependem das decisões, da ordem das células ou de outras execuções. Mantenha semente, IDs e horizonte para comparar caminhos comuns.
Mesma versão do modelo, cenário e ambiente Python geram resultados idênticos. A versão Python e hashes estão no pacote exportado.

## Políticas e metas

**Fixa:** repetir cada decisão por célula todos os meses, inclusive compras e investimentos.
**Manual:** uma política completa por mês. O formulário permite editar a grade; JSON aceita toda a sequência diretamente.
**Busca local:** adaptar decisões a metas ponderadas, com uma passagem por coordenadas e até 1 + 12 × número de células avaliações/mês.
Não é uma solução global nem uma recomendação industrial.

O algoritmo testa a política anterior e pequenos aumentos/reduções de pessoas (2), turnos (1), manutenção (0,25),
reposição (25% da capacidade inicial × material/unidade), investimento (10% da capacidade inicial) e plano (25% da capacidade inicial,
arredondado para inteiro e pelo menos 1). Cada alteração respeita os limites de validação. Uma melhoria estrita é mantida;
empates preservam a política atual. A ordem determinística é a ordem das células, depois os seis campos acima, redução antes de aumento.

O horizonte de avaliação tem dois meses, limitado pelo fim da simulação. Repete-se a decisão candidata no mês projetado.
O algoritmo conhece pedidos e recursos do mês corrente (os choques do mês já foram observados), mas assume **ausência de choques
no mês seguinte**. Portanto, a projeção não é uma promessa do resultado futuro. Os caminhos futuros realizados continuam usando a semente.

Cada meta pode ser alvo (`target`), teto (`upper`) ou piso (`lower`). Desvio = |valor − alvo|, max(0, valor − teto) ou
max(0, piso − valor), respectivamente. Distância = desvio / escala. Utilidade = 1 / (1 + distância).
Valor indefinido recebe utilidade zero. Nota mensal = soma(peso × utilidade) / soma(pesos); nota da busca = média dos meses projetados.
As alternativas, notas, política escolhida e contribuições de cada meta ficam no rastro. Metas são preferências suaves, não restrições duras.

## Limites de interpretação

Não há atrasos de fornecedor além da perda parcial do recebimento, sazonalidade automática, custos de contratação/demissão,
transferência de pessoal, restrição de espaço, vencimento de estoque, compras em lotes, capacidade de transporte ou otimização de chão de fábrica.
Os coeficientes de manutenção e choque são hipóteses didáticas arbitrárias. Compare experimentos como exercícios sobre essas hipóteses.
Na comparação, diferenças em datas, recursos, pedidos e semente são destacadas; elas impedem atribuir toda mudança apenas à política.
