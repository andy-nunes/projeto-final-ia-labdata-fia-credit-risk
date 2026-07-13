# Design da Camada Gold / ABT

Data: 2026-06-28

## Objetivo

Implementar o fluxo descrito em `HMDR_Camada_Gold_ABT.html` como um pipeline
Python executavel e uma DAG Airflow manual. O pipeline consome sete Parquets da
camada `clean`, cria agregados por cliente, monta e valida a ABT de treino e
publica exclusivamente `abt/abt_train.parquet` no MinIO.

A ABT final deve possuir uma linha por `SK_ID_CURR`, preservar `TARGET` da
`application_train_silver` e reproduzir as features e validacoes do notebook.

## Decisoes confirmadas

- A DAG nao possui schedule e usa `catchup=False`.
- O fluxo da DAG e estritamente sequencial.
- Cada origem possui tasks separadas para processamento e validacao.
- `bureau` e `bureau_balance` compartilham um TaskGroup por causa da ponte
  `SK_ID_BUREAU` para `SK_ID_CURR`.
- Qualquer resultado `[FAIL]` falha a task e bloqueia todas as etapas seguintes.
- Mensagens `[INFO]` permanecem informativas e nao reprovam tasks.
- O QA final exige exatamente 307.511 linhas.
- O bucket `abt` recebe apenas o arquivo final `abt_train.parquet`.
- Uma nova execucao bem-sucedida substitui o objeto final existente.
- A DAG usa `max_active_runs=1` para evitar concorrencia de memoria e I/O.
- O script direto sempre executa o pipeline completo, sem selecao parcial de
  etapas.

## Organizacao dos modulos

### `scripts/gold_transformations.py`

Concentra funcoes puras para:

- criar as features derivadas de `application_train`;
- agregar `bureau` por cliente;
- agregar `bureau_balance` por contrato e depois por cliente;
- agregar `POS_CASH_balance` por cliente;
- agregar `credit_card_balance` por cliente;
- agregar `previous_application` por cliente;
- colapsar pagamentos fracionados e agregar `installments_payments` por cliente;
- executar os LEFT JOINs que formam a ABT final;
- preencher somente flags `HAS_*` ausentes com zero.

### `scripts/gold_validations.py`

Concentra:

- schemas minimos exigidos antes de cada transformacao;
- resultados estruturados de QA;
- validacoes de cada agregado;
- validacao final da ABT;
- formatacao dos logs no estilo do notebook;
- excecao que carrega todas as regras reprovadas por etapa.

As validacoes executam todas as regras aplicaveis antes de levantar a excecao.
Assim, os logs mostram todas as falhas encontradas na mesma etapa.

### `scripts/abt_transform.py`

Concentra as fronteiras operacionais:

- cliente MinIO;
- download das entradas do bucket `clean`;
- escrita e leitura do staging local;
- chamadas para transformacoes e validacoes;
- upload final para o bucket `abt`;
- limpeza do staging apos sucesso;
- execucao sequencial por `main()` e bloco `if __name__ == "__main__"`.

Este e o unico modulo importado pela DAG. A execucao direta usa:

```bash
docker compose run --rm dev python scripts/abt_transform.py
```

### `dags/03_gold_abt_features.py`

Contem apenas a definicao da DAG, dos TaskGroups, das tasks e de suas
dependencias. Regras de negocio e acesso a dados permanecem em `scripts/`.

## Entradas e saida

Entradas no bucket `clean`:

- `application_train_silver.parquet`
- `bureau_silver.parquet`
- `bureau_balance_silver.parquet`
- `POS_CASH_balance_silver.parquet`
- `credit_card_balance_silver.parquet`
- `previous_application_silver.parquet`
- `installments_payments_silver.parquet`

Saida no bucket `abt`:

- `abt_train.parquet`

Nao existem uploads intermediarios. Downloads temporarios sao removidos ao fim
da task que os utiliza.

## Grafo da DAG

```text
application_train
  processar_application -> validar_application
        |
        v
bureau
  processar_bureau -> validar_bureau
  -> processar_bureau_balance -> validar_bureau_balance
        |
        v
pos_cash
  processar_pos_cash -> validar_pos_cash
        |
        v
credit_card
  processar_credit_card -> validar_credit_card
        |
        v
previous_application
  processar_previous_application -> validar_previous_application
        |
        v
installments
  processar_installments -> validar_installments
        |
        v
abt_final
  montar_abt -> validar_abt -> escrever_abt
```

Os sete TaskGroups sao `application_train`, `bureau`, `pos_cash`,
`credit_card`, `previous_application`, `installments` e `abt_final`.

## Staging e XCom

Artefatos intermediarios sao gravados em:

```text
Dados/.gold_staging/<run_id>/<etapa>/<arquivo>.parquet
```

O `run_id` e normalizado para formar um caminho seguro. Cada task retorna no
XCom apenas um dicionario pequeno com identificador da etapa, caminho do
artefato, quantidade de linhas e status de QA. DataFrames e conteudo Parquet nao
trafegam pelo XCom.

Em caso de falha, o staging do `run_id` e preservado para diagnostico. Depois do
upload final bem-sucedido, todo o staging daquele `run_id` e removido. O
diretorio `Dados/.gold_staging` deve ser adicionado ao `.gitignore`.

## Transformacoes

As transformacoes seguem o notebook:

- application: `EXT_SOURCE_MEAN`, `EXT_SOURCE_CNT`, flags de ausencia das
  fontes externas, `CREDIT_INCOME_RATIO`, `ANNUITY_INCOME_RATIO`,
  `LOG_AMT_CREDIT` e `DAYS_EMPLOYED_YEARS` quando as colunas de origem existirem;
- bureau: contagens de contratos por status, exposicao, divida, atraso e
  `HAS_BUREAU`;
- bureau balance: contagens por status, taxas de atraso e
  `HAS_BUREAU_BALANCE`, usando a ponte com `bureau`;
- POS/CASH: meses, contratos, atraso, taxa de atraso e `HAS_POS_CASH`;
- cartao: meses, atrasos, saldo, limite, utilizacao, saques ATM e
  `HAS_CREDIT_CARD`;
- propostas anteriores: contagens por status, taxas, montantes, decisao e
  `HAS_PREVIOUS_APP`;
- parcelas: consolidacao por parcela antes do agregado por cliente, montantes,
  atrasos, calote, pagamento parcial, taxas e `HAS_INSTALLMENTS`.

As tabelas auxiliares sao filtradas para os IDs existentes na
`application_train_silver`. A montagem final usa LEFT JOIN a partir da base de
application enriquecida.

## Validacoes e logs

Cada entrada passa por uma verificacao explicita de colunas obrigatorias antes
do processamento. Colunas usadas condicionalmente pelo notebook continuam
condicionais; colunas indispensaveis para joins, groupbys e calculos sao
obrigatorias.

Os logs seguem o estilo do notebook:

```text
[QA] bureau_gold
 -> [PASS] SK_ID_CURR unico
 -> [FAIL] regra reprovada
 -> [INFO] metrica diagnostica
--- Fim QA bureau_gold ---
```

Um `[FAIL]` levanta uma excecao apos todas as regras da etapa serem registradas.
Isso marca a task como `failed`, bloqueia o restante da cadeia e impede qualquer
escrita no bucket `abt`.

O QA final verifica:

- exatamente 307.511 linhas;
- igualdade de linhas com a application carregada;
- unicidade de `SK_ID_CURR`;
- ausencia de nomes de colunas duplicados;
- `TARGET` preservado por `SK_ID_CURR`;
- taxa de `TARGET` estritamente entre 5% e 12%;
- ausencia de infinitos em colunas numericas;
- flags `HAS_*` no dominio `{0, 1}`;
- coerencia entre `HAS_BUREAU` e `BUREAU_CNT_CREDITS`;
- cobertura das principais fontes e percentual de nulos das features derivadas
  como informacoes nao bloqueantes.

## Execucao direta e idempotencia

O `main()` cria um `run_id`, executa todas as etapas na mesma ordem da DAG e
interrompe no primeiro erro. A mensagem final identifica a etapa reprovada; a
excecao de QA lista todas as regras `[FAIL]` daquela etapa. O processo retorna
codigo `1` quando falha e `0` quando conclui o upload.

O objeto `abt/abt_train.parquet` so e substituido depois da aprovacao do QA
final. Portanto, uma falha mantem intacta a ultima ABT aprovada no MinIO.

## Testes

A suite permanece em pytest e pytest-mock:

- `tests/test_gold_transformations.py`: features, agregacoes, ponte bureau,
  parcelas fracionadas e merge;
- `tests/test_gold_validations.py`: schemas, acumulacao de falhas, logs, regras
  informativas e volumetria exata;
- `tests/test_abt_transform.py`: MinIO simulado, staging, metadados de XCom,
  bloqueio de upload, overwrite, preservacao e limpeza;
- `tests/test_gold_dag.py`: configuracao manual, sete TaskGroups, tasks e
  dependencias sequenciais.

Validacoes finais no ambiente Docker:

```bash
docker compose exec -T airflow python -m pytest /opt/airflow/tests -q
docker compose exec -T airflow python -m py_compile \
  /opt/airflow/scripts/gold_transformations.py \
  /opt/airflow/scripts/gold_validations.py \
  /opt/airflow/scripts/abt_transform.py \
  /opt/airflow/dags/03_gold_abt_features.py
docker compose exec -T airflow airflow dags list-import-errors
docker compose exec -T airflow airflow dags list
```

## Documentacao e manutencao

A implementacao esta documentada em `README.md`,
`docs/architecture/ambiente-docker-e-dados.md`, `docs/pipeline/dags/README.md` e
`docs/pipeline/dags/03_gold_abt_features.md`. Os arquivos locais ignorados `AGENTS.md` e
`SKILL.md` devem permanecer sincronizados com este contrato.

Todo codigo Python novo, inclusive modulos de teste, fixtures, classes fake,
helpers e funcoes `test_*`, deve possuir docstring em portugues. A suite Gold
atual segue esse padrao integralmente.
