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
