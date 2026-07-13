# Configuracao Do Modelo

Este documento explica o arquivo `config/model_config.yaml`, que centraliza
regras de negocio, caminhos, features e parametros usados no treinamento,
inferencia via API e dashboard Streamlit.

## Papel Do Arquivo

O `model_config.yaml` e a fonte versionada de configuracao do modelo LightGBM.
Ele e carregado por `scripts/model_config.py` e consumido por:

- `scripts/train.py`: treinamento, split, selecao de features,
  threshold e publicacao de artefatos.
- `scripts/predict.py`: montagem da matriz de predicao, threshold, faixas de
  risco e carregamento de modelo/ABT.
- `app/main.py`: endpoint de saude e endpoint `POST /score`.
- `app/dashboard.py`: campos editaveis, campos somente leitura e URL da API.

O objetivo e evitar regras espalhadas pelo codigo. Mudancas de politica, como
threshold de negocio, trilho de features ou caminho de artefato, devem passar
por esse arquivo sempre que fizer sentido.

## Estrutura Geral

O arquivo possui as secoes abaixo:

```yaml
project:
reproducibility:
splits:
business:
business_rules:
features:
model:
paths:
api:
minio:
metadata:
```

## `project`

Define identificadores centrais do problema.

- `name`: nome do projeto para rastreabilidade.
- `target_column`: coluna alvo usada como gabarito historico. Atualmente
  `TARGET`.
- `id_column`: chave de cliente usada em consultas. Atualmente `SK_ID_CURR`.

`id_column` nunca deve entrar no treinamento do modelo. Ele existe para buscar
o cliente no holdout e para auditoria no frontend.

## `reproducibility`

Controla reproducibilidade e checagens de integridade.

- `random_state`: semente fixa usada em split e treinamento.
- `full_dataset_rows`: quantidade esperada de linhas na ABT completa.

O valor atual de `full_dataset_rows` e `307511`. Ele serve como barreira contra
treinar com uma ABT incompleta ou inesperada.

## `splits`

Define a divisao da ABT para treino, teste e holdout de demonstracao.

Valores atuais:

- `train`: `0.80`
- `test`: `0.199`
- `demo_holdout`: `0.001`

As tres parcelas devem somar `1.0`. Essa validacao acontece em
`scripts/model_config.py` ao carregar o YAML.

O `demo_holdout` gera `Dados/abt/abt_demo_holdout.parquet`, usado pela API e
pelo Streamlit para consultas por `SK_ID_CURR`. Esse conjunto nao e usado para
treinar o modelo; ele existe para demonstracao e auditoria visual.

## `business`

Define escolhas de avaliacao de negocio durante treinamento.

- `f_beta`: peso do recall em relacao a precision. O valor `2` representa F2,
  priorizando reducao de falsos negativos.
- `primary_metric`: metrica principal de selecao. Atualmente `pr_auc`.

No problema de credito, falso negativo significa aprovar um cliente que se
mostra inadimplente no historico. Por isso o projeto prioriza metricas que
destaquem a classe minoritaria e penalizem esse tipo de erro.

## `business_rules`

Define regras operacionais de decisao.

- `business_threshold`: corte de probabilidade usado para transformar score em
  classe binaria.

Valor atual:

```yaml
business_threshold: 0.08
```

Interpretacao:

- `probability < 0.08`: `prediction = 0`, cliente aprovado.
- `probability >= 0.08`: `prediction = 1`, cliente reprovado.

A mesma regra alimenta o dashboard:

- abaixo de `threshold * 0.4`: `Baixo risco`;
- de `threshold * 0.4` ate abaixo de `threshold`: `Risco moderado`;
- a partir de `threshold`: `Alto risco`.

Com `threshold=8%`, as faixas sao:

- abaixo de `3,2%`: baixo risco;
- de `3,2%` ate abaixo de `8%`: risco moderado;
- `8%` ou mais: alto risco.

## `features`

Controla quais colunas entram no modelo e quais aparecem no dashboard.

### `set`

Define o trilho ativo:

- `full`: usa todas as colunas disponiveis da ABT, exceto `drop_cols`.
- `core`: usa apenas o bloco `core`.
- `extended`: usa `core` + `extended_extra`.

O valor atual e `full`.

### `drop_cols`

Colunas removidas da matriz de treinamento e predicao.

Atualmente:

- `SK_ID_CURR`
- `TARGET`

`SK_ID_CURR` e removida para impedir que o modelo aprenda identificadores de
cliente. `TARGET` e removida para evitar vazamento do gabarito na predicao.

### `categorical_features`

Lista de colunas tratadas como categoricas pelo LightGBM.

Essas colunas sao normalizadas em `scripts/predict.py` para bater com as
categorias conhecidas pelo modelo serializado. Isso evita erro quando o
dashboard envia valores em formatos equivalentes, como `1`, `Y`, `true` ou
texto com diferencas de caixa.

### `editable_features`

Features que o usuario pode alterar no Streamlit para simulacao what-if.

Atualmente:

- `AMT_CREDIT`
- `AMT_ANNUITY`
- `NAME_EDUCATION_TYPE`
- `NAME_INCOME_TYPE`
- `OCCUPATION_TYPE`
- `ORGANIZATION_TYPE`

`ORGANIZATION_TYPE` representa o tipo de organizacao ou setor do empregador e
aparece no dashboard como uma selecao categorica, usando as categorias
principais observadas na ABT.

Os campos monetarios `AMT_CREDIT` e `AMT_ANNUITY` possuem validacao adicional
no dashboard:

- aceitam apenas int/float textual, incluindo virgula decimal;
- rejeitam vazio, texto, zero, negativos e valores fora dos limites;
- limite inferior: `1`;
- limite superior de `AMT_CREDIT`: `4.050.000,00`;
- limite superior de `AMT_ANNUITY`: `258.025,50`.

Esses tetos foram extraidos de `abt_train.parquet`, usando o maior valor
observado em cada coluna da ABT de treino. A justificativa e evitar simulacoes
fora do dominio conhecido pelo LightGBM. Valores acima do maximo visto no
treinamento seriam extrapolacao operacional e poderiam reduzir a confiabilidade
do score e dos fatores explicativos.

### Recálculo online de derivadas financeiras

No endpoint `POST /score`, os overrides sao aplicados no dossie do cliente antes
da montagem da matriz de inferencia. Quando `AMT_CREDIT` ou `AMT_ANNUITY` sao
alterados, `scripts/predict.py` recalcula as derivadas financeiras diretamente
impactadas:

- `CREDIT_INCOME_RATIO = AMT_CREDIT / AMT_INCOME_TOTAL`
- `ANNUITY_INCOME_RATIO = AMT_ANNUITY / AMT_INCOME_TOTAL`
- `LOG_AMT_CREDIT = log1p(max(AMT_CREDIT, 0))`

Divisoes por zero ou infinitos sao convertidos para nulo (`NaN`), mantendo o
padrao usado por pandas/numpy e evitando que o modelo receba valores infinitos.
Esse recálculo existe somente no caminho de inferencia online; as camadas
Silver e Gold continuam sendo a fonte offline da ABT.

### `readonly_features`

Features exibidas no Streamlit apenas para contexto.

Essas variaveis ajudam o usuario a entender o dossie do cliente, mas nao podem
ser editadas pela interface. Exemplos:

- scores externos `EXT_SOURCE_1`, `EXT_SOURCE_2`, `EXT_SOURCE_3`;
- idade e tempo de emprego;
- agregados de bureau, propostas anteriores e pagamentos historicos.

### `core` e `extended_extra`

Esses blocos permitem alternar o escopo do modelo sem reescrever codigo.

- `core`: conjunto essencial e mais simples.
- `extended_extra`: features derivadas adicionadas ao trilho `extended`.

Quando `features.set` e `core` ou `extended`, o loader valida se todas as
colunas solicitadas existem na ABT. Se alguma faltar, o treinamento ou a
predicao falha explicitamente.

## `model`

Define hiperparametros do LightGBM.

Campos atuais:

- `algorithm`: `lightgbm`
- `n_estimators`: quantidade de arvores.
- `num_leaves`: complexidade das folhas.
- `learning_rate`: taxa de aprendizado.
- `max_depth`: profundidade maxima.
- `subsample`: amostragem de linhas por arvore.
- `colsample_bytree`: amostragem de colunas por arvore.

Esses parametros sao usados pelo script de treinamento. Alterar qualquer um
deles exige retreinar o modelo e republicar o artefato.

## `paths`

Define caminhos locais e remotos.

Caminhos locais:

- `abt_path`: `Dados/abt/abt_train.parquet`
- `demo_holdout_path`: `Dados/abt/abt_demo_holdout.parquet`
- `model_artifact_path`: `artifacts/lightgbm_hcdr.pkl`
- `metadata_path`: `artifacts/model_metadata.json`

Caminhos S3/MinIO:

- `abt_path_s3`: `s3://abt/abt_train.parquet`
- `model_artifact_path_s3`: `s3://artifacts/lightgbm_hcdr.pkl`
- `metadata_path_s3`: `s3://artifacts/model_metadata.json`

`scripts/model_config.py` resolve esses caminhos com fallback. Em geral:

- se a variavel de ambiente correspondente existir, ela tem prioridade;
- para ABT, caminho local existente tem prioridade; caso contrario, usa S3;
- para modelo e metadados, o script pode preferir S3 quando o treinamento roda
  no Airflow/MinIO.

## Variaveis De Ambiente Com Prioridade

Alguns campos podem ser sobrescritos por variaveis de ambiente:

| Variavel | Uso |
| --- | --- |
| `ABT_PATH` | sobrescreve o caminho da ABT |
| `DEMO_HOLDOUT_PATH` | sobrescreve o caminho do holdout de demonstracao |
| `MODEL_PATH` | sobrescreve o caminho do modelo `.pkl` |
| `MODEL_METADATA_PATH` | sobrescreve o caminho dos metadados |
| `API_BASE_URL` | sobrescreve a URL usada pelo dashboard |

No `docker-compose.yml`, o servico `airflow` usa caminhos S3 para treinar e
publicar artefatos no MinIO. O servico `streamlit` usa `API_BASE_URL=http://api:8000`
para consumir o backend pela rede interna do Compose.

## `api`

Define a URL padrao da API para consumo pelo frontend.

```yaml
api:
  base_url: http://host.docker.internal:8000
```

Esse valor e util quando o dashboard roda fora do Compose. Dentro do Compose,
`API_BASE_URL=http://api:8000` sobrescreve o YAML.

## `minio`

Define endpoint e credenciais locais para o MinIO:

- `endpoint_url`: `http://minio:9000`
- `key`: `minioadmin`
- `secret`: `minioadmin`

Essas credenciais sao de desenvolvimento local. Nao devem ser tratadas como
segredo de producao.

## `metadata`

Registra informacoes de versao e descricao do artefato.

- `version`: versao semantica do artefato/configuracao.
- `description`: resumo do modelo treinado.

O treinamento exporta tambem `model_metadata.json`, contendo metadados
operacionais como metricas, threshold, colunas de features e caminhos usados.

## O Que Exige Retreinamento

Exige retreinar e republicar o modelo:

- alterar `features.set`, `core`, `extended_extra`, `drop_cols` ou
  `categorical_features`;
- alterar hiperparametros em `model`;
- alterar splits relevantes para treino/teste;
- alterar a ABT de entrada.

Pode nao exigir retreinamento, mas exige revalidacao:

- alterar `business_rules.business_threshold`;
- alterar `editable_features` ou `readonly_features`;
- alterar `api.base_url`;
- alterar caminhos para apontar para outro artefato ja treinado.

Mesmo quando nao ha retreinamento, a mudanca deve ser testada com API e
dashboard, porque pode alterar a decisao operacional ou a experiencia do
usuario.

## Checklist De Alteracao

Ao alterar `config/model_config.yaml`:

1. Confirme que os splits somam `1.0`.
2. Se mudar features do modelo, rode treinamento novamente.
3. Se mudar threshold, valide matriz de confusao e exemplos do holdout.
4. Se mudar campos do dashboard, valide `app/dashboard.py` com AppTest.
5. Rode testes proporcionais:

```bash
docker compose exec -T streamlit python -m pytest /app/tests/test_model_config.py /app/tests/test_predict.py -q
docker compose exec -T airflow python -m pytest /opt/airflow/tests -q
```

6. Atualize documentacao quando a mudanca afetar comportamento, comandos,
   features, paths ou regras de negocio.
