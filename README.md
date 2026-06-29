# projeto-final-ia-labdata-fia-credit-risk

Projeto Final MBA FIA para o desafio de Credit Risk com dados da competicao
Home Credit Default Risk.

## Ambiente com Docker

### Primeiros passos

1. Garanta que o Docker e o Docker Compose estejam instalados.
2. Crie `~/.kaggle/kaggle.json` com suas credenciais da Kaggle.
3. Suba o ambiente com `docker compose build` e depois `docker compose up -d minio airflow streamlit`.
4. Verifique os serviços em `http://localhost:8080`, `http://localhost:9001` e `http://localhost:8501`.
5. Se quiser carregar os dados brutos, dispare a DAG `download_kaggle_to_minio` no Airflow.
6. Para gerar a camada limpa, dispare `raw_to_clean_silver`; cada TaskGroup
   processa, valida e publica uma tabela de forma isolada.
7. Para gerar a ABT de treino, dispare `clean_to_abt_gold` após a conclusão da
   Silver.

Construa a imagem:

```bash
docker compose build
```

Abra um shell dentro do ambiente:

```bash
docker compose run --rm dev
```

Suba os servicos locais de orquestracao, storage e app:

```bash
docker compose up -d minio airflow streamlit
```

Na inicializacao, o container do Airflow executa `airflow db migrate` e
`airflow dags reserialize` antes do `airflow standalone`. Isso garante que, em
clones limpos, as DAGs montadas em `./dags` sejam serializadas no banco local e
aparecam na listagem/UI sem comando manual adicional.

O Airflow tambem usa hostname fixo `airflow` e define
`AIRFLOW__CORE__HOSTNAME_CALLABLE=scripts.airflow_config.get_airflow_hostname`
para evitar URLs internas de logs sem host, como `http://:8793/log/...`, em
ambientes Docker diferentes.

Se precisar reiniciar tudo do zero, use:

```bash
docker compose down -v
```

Baixe os dados brutos da competicao Kaggle e envie para o bucket `raw` no MinIO
disparando manualmente a DAG `download_kaggle_to_minio` no Airflow:

```bash
docker compose exec -T airflow airflow dags unpause download_kaggle_to_minio
docker compose exec -T airflow airflow dags trigger download_kaggle_to_minio
```

Execute os oito pipelines Silver. Cada tabela possui um TaskGroup isolado com
`coletar_e_processar -> validar -> escrever_clean`; o bucket `clean` só recebe
Parquets aprovados:

```bash
docker compose exec -T airflow airflow dags trigger raw_to_clean_silver
```

O pipeline completo também pode ser executado diretamente para todas as tabelas
ou para uma seleção:

```bash
docker compose run --rm dev python scripts/silver_pipeline.py bureau application_train
```

O QA registra `[PASS]`, `[WARNING]` e `[FAIL]`. Somente `[FAIL]` bloqueia a
publicação da tabela. O staging aprovado é removido após o upload; staging
reprovado permanece em `Dados/.silver_staging` para diagnóstico.

Gere a ABT Gold com sete TaskGroups e 17 tasks estritamente sequenciais:

```bash
docker compose exec -T airflow airflow dags trigger clean_to_abt_gold
```

O mesmo fluxo pode ser executado diretamente, sempre por completo:

```bash
docker compose run --rm dev python scripts/gold_pipeline.py
```

As entradas são sete Parquets do bucket `clean`. Os agregados temporários ficam
em `Dados/.gold_staging/<run_id>` e não trafegam pelo XCom. Somente após todas
as validações `[PASS]` o pipeline substitui `abt/abt_train.parquet`; `[INFO]`
não reprova, `[FAIL]` bloqueia a cadeia e preserva o staging para diagnóstico.

Na inicializacao do Streamlit sao criados os buckets `raw`, `clean` e `abt`.

Para o download funcionar, o arquivo de credenciais Kaggle deve existir em
`~/.kaggle/kaggle.json` na maquina host.

Acessos locais:

- Airflow: http://localhost:8080 (auth local simplificada via SimpleAuthManager)
- MinIO Console: http://localhost:9001 (`minioadmin` / `minioadmin`)
- MinIO API: http://localhost:9000
- Streamlit: http://localhost:8501

Todos esses servicos montam a pasta `Dados` dentro dos containers.

## Dados

Arquivos CSV nao devem ser versionados. A pasta `Dados/` existe para volumes
locais e artefatos intermediarios, mas os dados brutos baixados pelo Kaggle
devem ser armazenados no bucket `raw` do MinIO.

Para inspecionar ou copiar arquivos entre MinIO e `Dados`, use o servico
`minio-client`. Consulte `docs/minio-client.md`.

Para detalhes das DAGs Airflow disponiveis, consulte `docs/dags/README.md`.

## Documentacao

- `docs/ambiente-docker-e-dados.md`: arquitetura local, servicos e fluxo de
  dados entre os buckets.
- `docs/camada-silver.md`: transformacoes, staging e QA de `raw` para `clean`.
- `docs/camada-gold-abt-design.md`: transformacoes, staging e QA de `clean`
  para `abt`.
- `docs/dags/README.md`: indice e comandos das DAGs manuais.
- `docs/minio-client.md`: inspecao e copia de objetos no MinIO.

## Validacao do projeto

Depois de alterar DAGs, scripts ou testes, execute no ambiente Airflow:

```bash
docker compose exec -T airflow python -m pytest /opt/airflow/tests -q
docker compose exec -T airflow airflow dags list-import-errors
docker compose exec -T airflow airflow dags list
```

Todo modulo, classe, helper, fixture e funcao de teste Python novo deve possuir
docstring em portugues. A suite usa `pytest` e `pytest-mock`.
