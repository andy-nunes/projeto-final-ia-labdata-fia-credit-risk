# MinIO Client

Este projeto usa o MinIO como storage S3 local. Os buckets nao devem ser
tratados como pastas montadas diretamente no host, porque o MinIO grava os
objetos em uma estrutura interna propria. Para inspecionar ou copiar arquivos
entre buckets e a pasta local `Dados`, use o servico auxiliar `minio-client`.

## Como funciona

O servico `minio-client` usa a imagem oficial `minio/mc` e roda na mesma rede do
`docker-compose`. Ao iniciar, ele cria o alias `local` apontando para o MinIO:

```bash
local -> http://minio:9000
```

Credenciais usadas no ambiente local:

```text
usuario: minioadmin
senha: minioadmin
```

A pasta `./Dados` do host fica montada no container em `/Dados`. Isso permite
copiar arquivos entre o MinIO e o diretorio local sem instalar ferramentas
extras na maquina.

## Listar buckets e objetos

Listar buckets:

```bash
docker compose run --rm minio-client ls local
```

Listar objetos do bucket `raw`:

```bash
docker compose run --rm minio-client ls local/raw
```

Listar objetos de forma recursiva:

```bash
docker compose run --rm minio-client ls --recursive local/raw
```

## Baixar arquivos do bucket para `Dados`

Baixar um arquivo especifico:

```bash
docker compose run --rm minio-client cp local/raw/application_train.csv /Dados/raw/application_train.csv
```

Baixar todo o bucket `raw` para `Dados/raw`:

```bash
docker compose run --rm minio-client mirror local/raw /Dados/raw
```

Esse comando cria uma copia local para analise, notebooks ou verificacoes
manuais. A fonte de verdade continua sendo o bucket no MinIO.

## Enviar arquivos locais para o bucket

Enviar um arquivo especifico:

```bash
docker compose run --rm minio-client cp /Dados/raw/application_train.csv local/raw/application_train.csv
```

Enviar todos os arquivos de `Dados/raw` para o bucket `raw`:

```bash
docker compose run --rm minio-client mirror /Dados/raw local/raw
```

Use esse fluxo apenas quando houver uma razao clara para promover arquivos
locais para o MinIO. Para os dados brutos do Kaggle, o fluxo principal do
projeto e a DAG `download_kaggle_to_minio`.

## Casos de uso

- Conferir rapidamente se os buckets `raw`, `clean`, `abt` e `artifacts` existem.
- Verificar quais CSVs foram carregados pela DAG `download_kaggle_to_minio`.
- Baixar uma copia local de `raw` para explorar os dados fora dos containers.
- Subir arquivos pontuais para testes manuais de pipeline.
- Espelhar um bucket para `Dados` antes de investigar problemas em notebooks ou
  scripts locais.

## Cuidados

- `mc mirror` sincroniza o destino com a origem e pode sobrescrever arquivos no
  destino.
- Arquivos CSV locais continuam ignorados pelo Git por causa da regra `*.csv`.
- Evite tratar `Dados/raw` como fonte oficial dos dados. O bucket `raw` no MinIO
  e a referencia do projeto.
- A DAG de download nao roda automaticamente ao subir os containers; ela deve
  ser disparada manualmente no Airflow.
