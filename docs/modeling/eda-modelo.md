# Guia para iniciantes: Modelagem de Risco de Crédito

Este documento explica, passo a passo e em linguagem introdutória, o notebook
de comparação de modelos `notebooks/02_model_evaluation.ipynb` (e o treino
exploratório em `notebooks/03_train_exploration.ipynb`).

O objetivo não é ensinar cada detalhe da programação. O foco é compreender:

- qual problema o notebook tenta resolver;
- por que cada etapa existe;
- o que os modelos fazem;
- o que cada métrica significa;
- como interpretar os resultados sem tirar conclusões incorretas;
- quais limitações precisam ser consideradas antes de usar o modelo em uma
  situação real.

> **Resumo em uma frase:** o notebook usa dados históricos para ensinar quatro
> modelos a ordenar clientes do menor para o maior risco de inadimplência.

---

## 1. Antes do notebook: qual é o problema?

Uma instituição financeira recebe uma solicitação de crédito e precisa decidir
se deve aprová-la, recusá-la ou analisá-la com mais cuidado.

O notebook tenta responder à seguinte pergunta:

> Com base nas informações disponíveis sobre um cliente, qual é o risco de ele
> enfrentar dificuldade para pagar as primeiras parcelas?

O modelo não conhece o futuro. Ele procura padrões em casos passados. Por
exemplo, pode aprender que certas combinações de renda, valor do crédito,
histórico de pagamentos e outras características aparecem com mais frequência
entre clientes que tiveram dificuldade de pagamento.

### O que é Machine Learning?

Machine Learning, ou aprendizado de máquina, é uma forma de construir regras a
partir de exemplos.

Em vez de escrever manualmente uma regra como:

```text
Se renda < X e dívida > Y, classifique como inadimplente.
```

entregamos ao algoritmo muitos exemplos de clientes e informamos o que aconteceu
com cada um. O algoritmo ajusta internamente suas regras para tentar distinguir
clientes de menor e maior risco.

### O que o modelo produz?

Para cada cliente, o modelo produz um **score**. Quanto maior o score, maior o
risco estimado pelo modelo.

Esse score pode parecer uma probabilidade, mas há uma ressalva importante: os
modelos foram treinados dando peso extra aos inadimplentes. Isso ajuda o modelo
a encontrá-los, porém pode distorcer a interpretação do número como uma
probabilidade real. Antes de afirmar que um score de `0,70` significa exatamente
“70% de chance”, seria necessário realizar uma etapa adicional chamada
**calibração de probabilidades**.

---

## 2. Mapa geral do fluxo de dados

O notebook começa depois de outras etapas do projeto:

```text
Dados brutos (raw)
        ↓
Dados limpos (clean / Silver)
        ↓
Tabela analítica (ABT / Gold)
        ↓
Treinamento e avaliação dos modelos
        ↓
Score de risco para cada cliente
```

### O que é a ABT?

ABT significa **Analytical Base Table**, ou tabela-base analítica.

Neste projeto, cada linha representa um cliente e cada coluna representa alguma
informação ou característica desse cliente. Exemplos:

- renda;
- valor solicitado;
- idade;
- histórico de crédito;
- atraso em parcelas anteriores;
- relacionamento entre crédito e renda.

O arquivo utilizado é `abt_train.parquet`.

### Vocabulário básico

| Termo | Significado simples |
|---|---|
| Observação | Um exemplo usado pelo modelo; neste caso, normalmente um cliente. |
| Feature | Informação usada para prever o risco, como renda ou idade. |
| Variável alvo | A resposta que o modelo tenta aprender. Neste notebook, `TARGET`. |
| Treino | Conjunto de exemplos que o modelo pode estudar. |
| Validação | Exemplos separados para testar o modelo depois do treino. |
| Modelo | Conjunto de regras matemáticas aprendidas a partir dos dados. |
| Previsão | Score ou classe produzida pelo modelo para um cliente. |
| Hiperparâmetro | Configuração escolhida antes do treino, como quantidade de árvores. |

---

## 3. Células iniciais: apresentação e configuração

### Célula 0 — apresentação

O notebook informa que vai comparar quatro algoritmos:

1. Regressão Logística;
2. Random Forest;
3. LightGBM;
4. XGBoost.

Eles recebem os mesmos dados de treino e são avaliados sobre o mesmo conjunto de
validação. Isso torna a comparação mais justa.

### Célula 1 — instalação opcional

A célula contém um comando comentado para instalar `lightgbm`, `xgboost` e
`scikit-learn` em ambientes como o Google Colab.

Ela não treina nenhum modelo. Sua finalidade é apenas preparar o ambiente caso
essas bibliotecas ainda não estejam instaladas.

### Células 2 e 3 — contexto, bibliotecas e configurações

O notebook importa ferramentas para:

- manipular tabelas (`pandas` e `numpy`);
- criar gráficos (`matplotlib` e `seaborn`);
- preparar dados e treinar modelos (`scikit-learn`);
- treinar os modelos LightGBM e XGBoost;
- medir tempo e apresentar resultados.

As principais configurações são:

| Configuração | Valor | Finalidade |
|---|---:|---|
| `RANDOM_STATE` | 42 | Tornar as divisões e treinos reproduzíveis. |
| `TEST_SIZE` | 20% | Reservar 20% dos clientes para validação. |
| `FULL_DATASET_ROWS` | 307.511 | Confirmar que a ABT está completa. |
| `BOOSTER_N_ESTIMATORS` | 500 | Usar inicialmente 500 árvores nos boosters. |
| `LGBM_NUM_LEAVES` | 63 | Controlar a complexidade das árvores LightGBM. |
| `LGBM_LEARNING_RATE` | 0,05 | Controlar o tamanho de cada correção no boosting. |

### O que é uma semente aleatória?

Algumas operações incluem sorteio, como separar clientes entre treino e
validação. A semente `42` faz o computador repetir o mesmo sorteio nas próximas
execuções.

Isso melhora a comparação e a reprodutibilidade, mas não significa que o
resultado será idêntico em qualquer computador, biblioteca ou quantidade de
processadores.

---

## 4. Etapa 1 do notebook: objetivo, alvo e desbalanceamento

### O que é `TARGET`?

`TARGET` é a resposta histórica que o modelo tenta aprender:

- `TARGET = 0`: cliente sem a dificuldade de pagamento definida pela base;
- `TARGET = 1`: cliente com dificuldade de pagamento nas primeiras parcelas.

É importante usar a definição exata da base. Neste contexto, `TARGET = 1` não
significa necessariamente qualquer atraso possível ou toda forma de prejuízo
financeiro.

### O que é desbalanceamento?

Os dados possuem:

- 91,93% de clientes com `TARGET = 0`;
- 8,07% de clientes com `TARGET = 1`.

Há muito mais exemplos da classe 0 do que da classe 1. Esse cenário é chamado
de **desbalanceamento de classes**.

Uma analogia: imagine uma caixa com 100 fichas, sendo 92 azuis e 8 vermelhas.
Se alguém responder “azul” sem sequer olhar para as fichas, acertará cerca de
92 vezes. A taxa de acerto parece excelente, mas essa pessoa é incapaz de
identificar uma única ficha vermelha.

Por isso, a acurácia isolada seria enganosa neste problema.

### Estratégias usadas contra o desbalanceamento

O notebook utiliza três medidas:

1. divisão estratificada, mantendo 8,07% de inadimplentes em treino e validação;
2. `class_weight='balanced'` na Regressão Logística e Random Forest;
3. `scale_pos_weight=11,39` no LightGBM e XGBoost.

O peso `11,39` vem aproximadamente desta razão:

```text
quantidade de clientes da classe 0 ÷ quantidade de clientes da classe 1
```

Isso faz um erro envolvendo a classe minoritária ter maior importância durante
o treino.

> **Cuidado:** dar mais peso à classe 1 não cria novos clientes nem corrige todos
> os problemas do desbalanceamento. Apenas altera o que o algoritmo considera
> mais caro errar.

---

## 5. Etapa 2: carregamento e controle de qualidade da ABT

O notebook carrega `abt_train.parquet` e executa verificações antes de treinar.

Resultado encontrado:

```text
307.511 linhas × 198 colunas
```

As verificações são:

### 5.1 Volumetria

Confirma que existem exatamente 307.511 clientes. Uma quantidade diferente pode
indicar arquivo incompleto, filtro indevido ou problema na construção da ABT.

### 5.2 Chave única

Confirma que `SK_ID_CURR` não está duplicado. Essa coluna identifica o cliente.
Se um cliente aparecesse várias vezes, ele poderia influenciar o treino mais do
que deveria.

### 5.3 Presença e taxa do alvo

Confirma que `TARGET` existe e que sua média está entre 5% e 12%. A taxa
observada foi 8,07%, coerente com a base esperada.

### 5.4 Ausência de infinito

Confirma que não existem valores `+∞` ou `-∞` nas colunas numéricas. Infinitos
podem surgir, por exemplo, em uma divisão por zero e prejudicar o treino.

### O que esse QA garante — e o que não garante

Essas verificações detectam problemas estruturais importantes. Elas não provam
que todas as informações estão corretas, que não existe viés ou que não ocorreu
vazamento de dados do futuro.

---

## 6. Etapa 3: separação entre `X` e `y`

O notebook separa os dados em:

- `X`: características entregues ao modelo;
- `y`: resposta correta, armazenada em `TARGET`.

Uma analogia escolar:

- `X` é o enunciado das questões;
- `y` é o gabarito.

O modelo estuda enunciados e gabaritos durante o treino. Na validação, recebe
apenas os enunciados e suas respostas são comparadas ao gabarito reservado.

### Por que remover `SK_ID_CURR`?

`SK_ID_CURR` é um identificador. Ele serve para localizar o cliente, não para
descrever seu comportamento financeiro.

Permitir que o modelo use identificadores pode fazê-lo decorar coincidências
sem valor para novos clientes.

### Por que remover `TARGET` de `X`?

Porque `TARGET` é a resposta. Entregá-la junto às features seria como deixar o
aluno consultar o gabarito durante a prova. Esse problema é chamado de
**vazamento de alvo**.

### Tipos de features

Após a remoção de identificador e alvo, restam 196 features:

- 180 numéricas;
- 16 categóricas.

Uma feature numérica contém valores como renda, idade ou quantidade. Uma
feature categórica contém rótulos como tipo de contrato, escolaridade ou tipo de
moradia.

### Valores ausentes

Algumas features de cartão de crédito têm mais de 71% de valores ausentes.
Isso não significa automaticamente erro. Um cliente pode não ter histórico de
cartão, e a própria ausência pode carregar informação.

O ponto importante é diferenciar:

- dado ausente porque a informação não se aplica;
- dado ausente por falha de coleta;
- dado ausente sem motivo conhecido.

O modelo enxerga apenas o valor ausente; a interpretação do motivo depende do
conhecimento do negócio e da origem dos dados.

---

## 7. Etapa 4: divisão estratificada em treino e validação

O notebook separa:

- 246.008 clientes para treino, equivalentes a 80%;
- 61.503 clientes para validação, equivalentes a 20%.

Ambos mantêm taxa de `TARGET = 1` em 8,07%.

### Por que não treinar com todos os clientes?

Se o modelo for avaliado nos mesmos clientes que estudou, pode parecer melhor
do que realmente é. Ele pode decorar peculiaridades do treino em vez de aprender
padrões que funcionem para pessoas novas.

Reservar a validação simula, de maneira limitada, a chegada de clientes que o
modelo ainda não viu.

### O que é generalização?

Generalização é a capacidade de funcionar bem em dados novos. É um dos objetivos
centrais de Machine Learning.

### O que é overfitting?

Overfitting, ou sobreajuste, ocorre quando o modelo aprende detalhes e ruídos do
treino, mas perde desempenho em novos dados.

Uma analogia: o aluno decora as respostas de uma lista de exercícios sem
entender a matéria. Ele vai bem na lista conhecida e mal em uma prova diferente.

---

## 8. Etapa 5: pré-processamento

Algoritmos diferentes exigem preparações diferentes.

### Regressão Logística e Random Forest

O pipeline do `scikit-learn` faz:

1. preenchimento dos nulos numéricos com a mediana;
2. preenchimento dos nulos categóricos com a categoria mais frequente;
3. transformação das categorias com One-Hot Encoding;
4. padronização para a Regressão Logística.

#### O que é mediana?

Depois de ordenar os valores, a mediana é o valor que fica no meio. Ela costuma
ser menos afetada por valores extremamente altos ou baixos do que a média.

#### O que é moda?

É o valor que aparece com maior frequência. No notebook, ela preenche categorias
ausentes.

#### O que é One-Hot Encoding?

Modelos matemáticos não entendem diretamente palavras como “Casa” e
“Apartamento”. O One-Hot transforma cada possibilidade em uma coluna de sim ou
não.

Exemplo:

| Moradia | Moradia_Casa | Moradia_Apartamento |
|---|---:|---:|
| Casa | 1 | 0 |
| Apartamento | 0 | 1 |

`handle_unknown='ignore'` evita erro se a validação contiver uma categoria não
vista durante o ajuste do pré-processamento.

#### O que é padronização?

Coloca features com escalas diferentes em uma referência comparável. Sem isso,
uma coluna em milhões poderia dominar numericamente outra coluna que varia entre
zero e um.

### LightGBM e XGBoost

Esses modelos conseguem trabalhar com valores ausentes e categorias de maneira
mais direta. O notebook preserva os nulos e converte as colunas categóricas para
um tipo próprio.

Essa decisão também preserva a possibilidade de o modelo aprender que a
ausência de uma informação está relacionada ao risco.

### Por que usar um pipeline?

O pipeline une preparação e modelo em uma sequência. Isso reduz o risco de
preparar treino e validação de maneiras diferentes e ajuda a evitar vazamento
de informação.

---

## 9. Etapa 6: os quatro modelos

Todos são treinados com o mesmo conjunto e avaliados no mesmo holdout.

### 9.1 Regressão Logística

É o modelo de referência, ou **baseline**.

Ela combina as features atribuindo pesos positivos ou negativos e transforma o
resultado em um score entre zero e um. É relativamente simples e seus efeitos
são mais fáceis de investigar.

Uma analogia é uma balança: cada característica adiciona ou remove peso do lado
do risco.

Pontos fortes:

- simples;
- rápida em muitos cenários;
- oferece uma referência clara;
- mais fácil de interpretar que modelos complexos.

Limitações:

- representa principalmente relações lineares;
- depende mais do pré-processamento;
- pode ter dificuldade com interações complexas entre features.

Resultado: **ROC-AUC 0,7672**.

### 9.2 Random Forest

Random Forest cria muitas árvores de decisão usando amostras e subconjuntos de
features diferentes. A previsão final combina os votos dessas árvores.

Uma analogia é consultar vários analistas, cada um vendo parte do caso, e
combinar suas opiniões.

Esse método é chamado de **bagging**: várias árvores são construídas com certo
grau de independência para reduzir a instabilidade de uma árvore isolada.

Resultado: **ROC-AUC 0,7612**.

### 9.3 LightGBM

LightGBM também usa árvores, mas trabalha em sequência. Cada nova árvore tenta
corrigir os erros cometidos pelas anteriores.

Uma analogia é revisar uma redação várias vezes: a primeira versão resolve os
problemas mais evidentes; as versões seguintes se concentram nos erros que ainda
restaram.

Esse processo é chamado de **gradient boosting**.

Pontos fortes:

- encontra relações não lineares;
- combinações entre features podem ser aprendidas;
- costuma funcionar bem em dados tabulares;
- lida nativamente com valores ausentes.

Resultado inicial: **ROC-AUC 0,7742**.

### 9.4 XGBoost

XGBoost pertence à mesma família de gradient boosting. Ele também cria árvores
sequenciais para corrigir erros anteriores, mas possui implementação e controles
de regularização diferentes.

Resultado: **ROC-AUC 0,7720**.

### Comparação inicial

| Posição | Modelo | ROC-AUC | Tempo de treino observado |
|---:|---|---:|---:|
| 1 | LightGBM | 0,7742 | 107,2 s |
| 2 | XGBoost | 0,7720 | 154,3 s |
| 3 | Regressão Logística | 0,7672 | 241,2 s |
| 4 | Random Forest | 0,7612 | 256,7 s |

Os tempos valem apenas para o ambiente em que o notebook foi executado. Eles
podem mudar bastante em outro computador.

As diferenças de AUC são pequenas. O ranking observado não prova, sozinho, que
o LightGBM sempre será superior em novos dados.

---

## 10. Métricas: como saber se o modelo é bom?

Esta é a parte mais importante para interpretar corretamente o notebook.

### 10.1 Score e threshold

O modelo primeiro produz um score contínuo. Para transformar esse score em uma
decisão binária, escolhemos um **threshold**, ou ponto de corte.

Com threshold de `0,50`:

```text
score < 0,50  → classificar como classe 0
score ≥ 0,50  → classificar como classe 1
```

Esse valor não é uma lei. Reduzir o threshold tende a encontrar mais
inadimplentes, mas também sinaliza mais bons pagadores como arriscados. Aumentar
o threshold faz o contrário.

Em crédito, o threshold deve considerar o custo financeiro e humano de cada tipo
de erro.

### 10.2 Matriz de confusão

A matriz de confusão organiza quatro possibilidades:

| Situação | Significado no exemplo de crédito |
|---|---|
| Verdadeiro negativo | Modelo indicou baixo risco e o cliente foi classe 0. |
| Verdadeiro positivo | Modelo indicou risco e o cliente foi classe 1. |
| Falso positivo | Modelo indicou risco, mas o cliente foi classe 0. |
| Falso negativo | Modelo indicou baixo risco, mas o cliente foi classe 1. |

#### Qual erro é pior?

Não existe resposta puramente técnica:

- falso negativo pode gerar perda financeira porque um risco não foi detectado;
- falso positivo pode negar ou encarecer crédito para um bom pagador, causando
  perda de cliente e possível tratamento injusto.

A decisão depende da política de crédito, custos, regulamentação e estratégia da
instituição.

### 10.3 Acurácia

Acurácia é a proporção total de previsões corretas:

```text
acurácia = quantidade de acertos ÷ quantidade total de previsões
```

No relatório do LightGBM com threshold `0,50`, a acurácia foi 0,78, ou 78%.

Isso não torna o modelo necessariamente ruim ou bom. Como 91,93% dos clientes
são classe 0, um modelo inútil que sempre respondesse classe 0 teria acurácia
maior, mas encontraria zero inadimplentes.

### 10.4 Precision, ou precisão da classe positiva

Precision responde:

> Entre os clientes que o modelo marcou como inadimplentes, quantos realmente
> pertenciam à classe 1?

```text
precision = verdadeiros positivos ÷ todos os classificados como positivos
```

Para os inadimplentes, o notebook obteve **0,21**.

Interpretação aproximada: de cada 100 clientes sinalizados como classe 1 pelo
modelo nesse threshold, cerca de 21 realmente eram classe 1 no conjunto de
validação.

Isso revela muitos falsos positivos.

### 10.5 Recall, sensibilidade ou taxa de detecção

Recall responde:

> Entre todos os clientes que realmente eram classe 1, quantos o modelo
> conseguiu encontrar?

```text
recall = verdadeiros positivos ÷ todos os positivos reais
```

O recall da classe 1 foi **0,60**.

Interpretação aproximada: o modelo encontrou 60% dos inadimplentes e deixou de
identificar 40%, usando threshold `0,50`.

### 10.6 F1-score

F1 combina precision e recall. Ele só fica alto quando ambos são razoavelmente
altos.

Sua fórmula é:

```text
F1 = 2 × (precision × recall) ÷ (precision + recall)
```

O F1 da classe inadimplente foi **0,31**.

Essa métrica é útil para resumir o equilíbrio entre detectar inadimplentes e não
gerar alertas excessivos. Porém, ela considera precision e recall com a mesma
importância; o negócio pode atribuir custos diferentes a cada erro.

### 10.7 Macro average e weighted average

O relatório mostra dois tipos de média:

- **macro avg**: calcula a métrica de cada classe e dá o mesmo peso a ambas;
- **weighted avg**: dá mais peso à classe que possui mais exemplos.

Em dados desbalanceados, a média ponderada pode parecer alta porque é dominada
pela classe majoritária. A macro average ajuda a observar as duas classes com o
mesmo peso.

### 10.8 Curva ROC

A curva ROC avalia vários thresholds, não apenas `0,50`.

Ela relaciona:

- taxa de verdadeiros positivos: quantos positivos foram encontrados;
- taxa de falsos positivos: quantos negativos foram sinalizados incorretamente.

Uma curva próxima da diagonal representa comportamento quase aleatório. Quanto
mais a curva se aproxima do canto superior esquerdo, melhor a capacidade de
separação.

### 10.9 ROC-AUC

AUC é a área sob a curva ROC. Ela varia geralmente entre `0,50` e `1,00`:

| ROC-AUC | Leitura intuitiva |
|---:|---|
| 0,50 | Ordenação semelhante ao acaso. |
| Entre 0,50 e 1,00 | Alguma capacidade de separar as classes. |
| 1,00 | Ordenação perfeita neste conjunto. |

Uma interpretação especialmente útil é:

> Se escolhermos aleatoriamente um cliente da classe 1 e um da classe 0, a AUC
> representa aproximadamente a chance de o modelo atribuir score de risco maior
> ao cliente da classe 1.

Assim, AUC `0,7742` significa aproximadamente 77,42% de chance de ordenar
corretamente um par formado por uma pessoa de cada classe.

> **AUC 0,7742 não significa 77,42% de previsões corretas.** Também não significa
> que a probabilidade individual de cada cliente está correta.

### Por que ROC-AUC é a métrica principal?

Porque o objetivo inicial é comparar a capacidade de **ranquear risco** em um
problema desbalanceado, sem depender de um único threshold.

Entretanto, a AUC não substitui métricas de negócio. Um modelo de crédito também
precisa ser avaliado por custo financeiro, aprovação, inadimplência, estabilidade,
calibração, equidade e conformidade regulatória.

---

## 11. Etapa 7: gráficos e interpretação do melhor modelo

### Curvas ROC

O primeiro gráfico sobrepõe as curvas dos quatro modelos no mesmo conjunto de
validação. Isso permite comparar sua capacidade de ordenação em diferentes
thresholds.

As curvas são próximas, coerentemente com AUCs entre 0,7612 e 0,7742.

### Matriz de confusão e relatório

O notebook seleciona o LightGBM por ter a maior AUC inicial e usa threshold
`0,50` para produzir classes.

Resultados principais:

| Classe | Precision | Recall | F1 |
|---|---:|---:|---:|
| Pagou (0) | 0,96 | 0,80 | 0,87 |
| Inadimplente (1) | 0,21 | 0,60 | 0,31 |

O modelo encontra uma parcela relevante dos inadimplentes, mas também sinaliza
muitos clientes da classe 0. Isso não deve ser resolvido escolhendo um threshold
arbitrário: é necessário medir os custos reais dos falsos positivos e falsos
negativos.

### Importância das features

O notebook exibe as 20 features mais utilizadas pelo LightGBM. Entre as mais
importantes aparecem:

- `ORGANIZATION_TYPE`;
- `EXT_SOURCE_3`;
- `EXT_SOURCE_MEAN`;
- `OCCUPATION_TYPE`;
- `EXT_SOURCE_1`;
- `DAYS_BIRTH`;
- `EXT_SOURCE_2`;
- informações de propostas anteriores, parcelas, renda e crédito.

#### O que “importante” significa aqui?

Significa que o modelo usou bastante aquela feature para melhorar suas divisões
internas. Não significa:

- que a feature causa inadimplência;
- que ela deve ser usada sem análise ética e legal;
- que aumentar ou diminuir seu valor mudará o risco na mesma proporção;
- que a posição será estável em outro conjunto de dados.

Para explicações mais confiáveis, seriam úteis análises adicionais, como
permutation importance ou SHAP, sempre acompanhadas de conhecimento do negócio.

---

## 12. Etapa 8: comparação consolidada

O ranking inicial foi:

```text
LightGBM             0,7742
XGBoost              0,7720
Regressão Logística  0,7672
Random Forest        0,7612
```

O LightGBM ficou em primeiro lugar, mas a maior diferença para o XGBoost foi de
apenas `0,0022` de AUC.

Para afirmar que essa diferença é consistente, seria necessário avaliar sua
variação em várias divisões ou períodos e, idealmente, usar um conjunto de teste
final que não participou de nenhuma escolha.

Um modelo ligeiramente pior em AUC pode ser preferível se for mais simples,
estável, rápido, calibrado, explicável ou adequado às exigências do negócio.

---

## 13. Etapa 9.1: validação cruzada com cinco folds

Um único holdout depende de uma única divisão aleatória. A validação cruzada
reduz essa dependência.

O conjunto de treino é dividido em cinco partes, chamadas folds:

```text
Rodada 1: valida no fold 1 e treina nos folds 2–5
Rodada 2: valida no fold 2 e treina nos folds 1, 3–5
...
Rodada 5: valida no fold 5 e treina nos folds 1–4
```

Cada cliente participa da validação uma vez e do treino quatro vezes.

Resultados do LightGBM:

```text
AUC média: 0,7665
Desvio-padrão: 0,0022
Folds: 0,7630; 0,7672; 0,7694; 0,7676; 0,7654
```

### Como interpretar?

Os resultados estão próximos, indicando estabilidade razoável entre essas cinco
divisões. A média da validação cruzada ficou abaixo da AUC `0,7742` do holdout,
mostrando que aquela divisão específica pode ter sido um pouco mais favorável.

O desvio-padrão pequeno não prova estabilidade futura. Todos os folds vêm do
mesmo conjunto e período histórico.

---

## 14. Etapa 9.2: undersampling

Undersampling reduz a quantidade de exemplos da classe majoritária.

O notebook mantém todos os inadimplentes do treino e sorteia a mesma quantidade
de clientes da classe 0. O novo conjunto fica aproximadamente 50% / 50%.

Resultados da Regressão Logística:

| Estratégia | ROC-AUC |
|---|---:|
| Dados completos com peso de classe | 0,7672 |
| Undersampling 50/50 | 0,7659 |

O undersampling não melhorou a AUC e descartou muitos exemplos de bons
pagadores. Neste experimento, usar os dados completos com peso de classe foi
ligeiramente melhor.

Isso não prova que undersampling nunca funciona. O resultado depende do modelo,
da amostra, da métrica e da forma de seleção dos exemplos.

---

## 15. Etapa 9.3: tuning do LightGBM

Tuning é a busca por melhores hiperparâmetros.

O notebook testa três combinações:

| `num_leaves` | `learning_rate` | ROC-AUC |
|---:|---:|---:|
| 31 | 0,05 | 0,7765 |
| 63 | 0,05 | 0,7742 |
| 31 | 0,03 | **0,7771** |

### O que é `num_leaves`?

Controla quantas regiões finais uma árvore pode criar. Mais folhas permitem
regras mais detalhadas, mas aumentam o risco de overfitting.

### O que é `learning_rate`?

Controla quanto cada árvore corrige o modelo. Um valor menor faz correções mais
cuidadosas e normalmente precisa ser combinado com uma quantidade adequada de
árvores.

### Cuidado metodológico importante

As combinações são comparadas repetidamente no mesmo holdout de 20%. Quando
escolhemos a melhor configuração olhando esse resultado, o holdout deixa de ser
uma avaliação completamente neutra e passa a participar da seleção.

Por isso, a AUC `0,7771` pode estar um pouco otimista.

Uma abordagem mais rigorosa seria:

1. treino para ajustar modelos;
2. validação interna ou cross-validation para escolher hiperparâmetros;
3. teste final, usado uma única vez depois que todas as decisões estiverem
   fechadas.

---

## 16. Etapa 9.4: custo × benefício do número de árvores

O notebook varia `n_estimators`, que representa a quantidade de árvores do
LightGBM.

| Árvores | ROC-AUC | Tempo observado |
|---:|---:|---:|
| 100 | 0,7721 | 34,8 s |
| 200 | 0,7754 | 51,9 s |
| 300 | **0,7757** | 72,7 s |
| 500 | 0,7742 | 107,6 s |
| 800 | 0,7697 | 145,0 s |

De 100 para 200 árvores, a AUC aumenta `0,0033`. De 200 para 300, o ganho é
apenas cerca de `0,0002`, enquanto o tempo continua aumentando.

Depois disso, a AUC cai. Isso pode indicar overfitting ou simplesmente variação
no holdout.

O notebook sugere **200 árvores** como compromisso entre desempenho e tempo:

```text
AUC 0,7754 em aproximadamente 51,9 segundos
```

Essa escolha é razoável para o experimento, mas não é universal. Custos de
predição, memória, retreinamento, estabilidade e infraestrutura também deveriam
entrar na decisão.

### O que é early stopping?

Early stopping interrompe o treinamento quando a métrica de validação deixa de
melhorar por várias rodadas.

O notebook decide não usá-lo na comparação principal porque, naquela
configuração, o LightGBM parava cedo demais. A solução correta para um pipeline
mais rigoroso é reservar uma validação interna para early stopping, sem usar o
conjunto de teste final para controlar o treinamento.

---

## 17. Etapa 10: fechamento e artefatos

O notebook conclui que:

- LightGBM foi o melhor dos quatro modelos na comparação inicial;
- os modelos possuem capacidade útil de ordenar risco;
- a validação cruzada apresentou variação pequena entre folds;
- o undersampling não melhorou a Regressão Logística;
- configurações mais complexas nem sempre aumentam a AUC;
- 200 árvores oferecem bom custo × benefício naquele ambiente.

A última célula mostra, mas não executa, comandos para salvar:

- o modelo treinado em um arquivo `joblib`;
- a tabela de comparação em CSV.

Portanto, executar o notebook como está não garante que o modelo será salvo. Os
comandos precisam ser descomentados e o modelo escolhido precisa estar claramente
definido.

---

## 18. O que o notebook demonstra

Com base nos resultados apresentados, podemos afirmar que:

- a ABT carregada possui a volumetria e estrutura esperadas;
- os quatro modelos foram comparados no mesmo holdout;
- todos apresentam AUC bem acima de 0,50 naquele conjunto;
- LightGBM obteve o melhor resultado inicial;
- a configuração testada com `num_leaves=31` e `learning_rate=0,03` atingiu AUC
  0,7771 no mesmo holdout;
- 200 árvores apresentaram uma relação favorável entre tempo e AUC no sweep;
- o desempenho variou pouco entre os cinco folds usados na validação cruzada.

---

## 19. O que o notebook ainda não demonstra

Ele não prova que:

- o modelo terá o mesmo desempenho em clientes futuros;
- os scores são probabilidades perfeitamente calibradas;
- o threshold `0,50` é adequado para a operação de crédito;
- o modelo é justo entre grupos de pessoas;
- as features importantes causam inadimplência;
- o modelo atende exigências legais e regulatórias;
- a pequena vantagem do LightGBM continuará em outros períodos;
- o modelo está pronto para produção.

---

## 20. Limitações metodológicas e riscos

### 20.1 Reutilização do holdout

O holdout é usado para comparar modelos, escolher hiperparâmetros e escolher a
quantidade de árvores. Quanto mais decisões são tomadas olhando o mesmo
conjunto, maior o risco de adaptar escolhas às particularidades dele.

### 20.2 Ausência de teste temporal

Crédito muda com economia, juros, emprego e comportamento. Uma divisão aleatória
mistura clientes do mesmo período. Uma validação temporal, treinando no passado
e testando em período posterior, se aproxima mais do uso real.

### 20.3 Calibração de probabilidade

O uso de pesos de classe melhora a atenção à classe minoritária, mas pode fazer
o score deixar de representar diretamente a frequência real de inadimplência.
Curvas de calibração, Brier score e métodos de calibração deveriam ser avaliados
se o número for usado como probabilidade.

### 20.4 Threshold sem custo de negócio

O corte `0,50` é apenas uma demonstração. A escolha operacional deve usar custos
de falso positivo e falso negativo, capacidade de análise manual, retorno
esperado e limites regulatórios.

### 20.5 Equidade e variáveis sensíveis

Um modelo pode reproduzir desigualdades históricas mesmo sem receber diretamente
uma variável sensível. Outras features podem funcionar como aproximações. É
necessário avaliar desempenho, taxa de aprovação e erros por grupos relevantes,
com suporte jurídico e de negócio.

### 20.6 Explicabilidade

Importância global de feature não explica completamente uma decisão individual.
Crédito costuma exigir justificativas compreensíveis e auditáveis.

### 20.7 Monitoramento

Mesmo um modelo aprovado pode piorar com o tempo. Produção exige monitoramento
de mudanças nos dados, performance, calibração, estabilidade e impacto de
negócio.

---

## 21. Próximos passos recomendados

Uma evolução prudente seria:

1. definir treino, validação e teste final independentes, preferencialmente com
   recorte temporal;
2. escolher hiperparâmetros somente no treino/validação;
3. avaliar uma única vez no teste final;
4. calibrar as probabilidades;
5. escolher threshold com custos reais de negócio;
6. medir performance e erros por segmentos relevantes;
7. comparar AUC com métricas de negócio e calibração;
8. salvar o pipeline completo, não apenas o estimador;
9. criar um fluxo separado de predição;
10. monitorar o modelo depois da implantação.

---

## 22. Perguntas frequentes

### AUC 0,77 significa 77% de acerto?

Não. AUC mede principalmente capacidade de ordenação entre as classes. A taxa
de acerto depende de um threshold e é medida pela acurácia.

### O LightGBM prevê quem certamente ficará inadimplente?

Não. Ele produz uma estimativa de risco baseada em padrões históricos e pode
errar nos dois sentidos.

### Por que a acurácia do modelo é menor que 91,93%?

Porque um modelo que sempre previsse a classe 0 teria 91,93% de acurácia, mas
não encontraria nenhum inadimplente. O modelo treinado aceita mais falsos
positivos para detectar parte da classe 1.

### O melhor modelo é sempre o que possui maior AUC?

Não. A escolha também depende de estabilidade, calibração, custo, explicação,
latência, manutenção, equidade e requisitos regulatórios.

### Por que existem tantos valores ausentes?

Algumas informações não se aplicam a todos os clientes. Por exemplo, alguém sem
histórico de cartão pode ter várias features de cartão ausentes. Ainda é preciso
investigar a origem de cada ausência.

### Mais árvores sempre melhoram o modelo?

Não. O experimento mostrou aumento até certo ponto e depois queda. Complexidade
excessiva pode causar overfitting e aumentar custo sem benefício.

### Feature importante é causa de inadimplência?

Não. Importância mostra associação e uso pelo modelo, não relação causal.

### Por que não usar `application_test`?

Essa tabela não possui `TARGET`, portanto o notebook não consegue calcular suas
métricas nela. Ela pode ser usada para gerar scores depois que o pipeline final
estiver definido.

---

## 23. Glossário

| Termo | Explicação |
|---|---|
| ABT | Tabela analítica com uma linha por cliente e features para modelagem. |
| Algoritmo | Procedimento usado para aprender um modelo a partir dos dados. |
| Baseline | Modelo de referência usado para saber se soluções mais complexas realmente melhoram. |
| Bagging | Combinação de modelos treinados com amostras diferentes, como na Random Forest. |
| Boosting | Sequência de modelos em que cada novo componente tenta corrigir erros anteriores. |
| Calibração | Verificação e ajuste para que scores correspondam melhor a probabilidades reais. |
| Classe | Categoria que queremos prever; neste caso, 0 ou 1. |
| Cross-validation | Avaliação que alterna várias partes dos dados entre treino e validação. |
| Data leakage | Uso indevido de informação que não estaria disponível no momento real da previsão. |
| Feature | Informação entregue ao modelo. |
| Fit | Processo de treinamento ou ajuste do modelo. |
| Holdout | Parte dos dados reservada e não usada no treino daquele modelo. |
| Hiperparâmetro | Configuração definida antes do treinamento. |
| Imputação | Preenchimento de valores ausentes. |
| Inferência | Uso do modelo treinado para gerar uma previsão. |
| Overfitting | Quando o modelo aprende demais o treino e generaliza mal. |
| Pipeline | Sequência organizada de preparação e modelagem. |
| Score | Número produzido pelo modelo para representar risco. |
| Seed | Valor que ajuda a repetir operações aleatórias. |
| Target | Resposta histórica que o modelo tenta aprender. |
| Threshold | Ponto de corte que transforma score em uma classe. |
| Tuning | Busca por configurações melhores para o modelo. |
| Undersampling | Redução da quantidade de exemplos da classe majoritária. |

---

## Conclusão

O notebook é uma boa demonstração de comparação inicial de modelos para dados
tabulares e desbalanceados. O LightGBM apresentou a melhor ROC-AUC entre os
quatro modelos, e os experimentos ajudaram a entender estabilidade, pesos de
classe, hiperparâmetros e custo computacional.

A principal leitura é que o modelo consegue **ordenar risco melhor que o acaso**,
mas ainda não está automaticamente pronto para tomar decisões reais. Antes
disso, são necessárias avaliação final independente, calibração, definição de
threshold por custo de negócio, análise de equidade, explicabilidade e
monitoramento.
