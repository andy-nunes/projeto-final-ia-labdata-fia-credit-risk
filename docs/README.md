# Documentacao do Projeto

Indice da documentacao tecnica e operacional do motor de decisao de credito
Home Credit Default Risk.

## Arquitetura

- [`architecture/ambiente-docker-e-dados.md`](architecture/ambiente-docker-e-dados.md):
  ambiente Docker, servicos, volumes e dados locais.
- [`architecture/mlops-monitoramento-e-automacao.md`](architecture/mlops-monitoramento-e-automacao.md):
  proposta de monitoramento (iii) e automacao / agentes de IA (iv).
- [`architecture/arquitetura-mlops-home-credit.png`](architecture/arquitetura-mlops-home-credit.png)
  e [`SVG`](architecture/arquitetura-mlops-home-credit.svg): diagrama da solucao.

## Pipeline (Medalhao)

- [`pipeline/camada-silver.md`](pipeline/camada-silver.md): transformacoes, staging
  e QA de `raw` para `clean`.
- [`pipeline/camada-gold-abt-design.md`](pipeline/camada-gold-abt-design.md):
  transformacoes, staging e QA de `clean` para `abt`.
- [`pipeline/dags/README.md`](pipeline/dags/README.md): indice e comandos das DAGs
  manuais Airflow.

## Modelagem

- [`modeling/model-config.md`](modeling/model-config.md): guia do
  `config/model_config.yaml`.
- [`modeling/exemplos-confusion-matrix.md`](modeling/exemplos-confusion-matrix.md):
  exemplos de TN, TP, FN e FP.
- [`modeling/eda-modelo.md`](modeling/eda-modelo.md): guia introdutorio da
  modelagem (leitura para banca).

## Operacao

- [`operations/catalogo-abt.md`](operations/catalogo-abt.md): catalogo pesquisavel
  da ABT no Streamlit.
- [`operations/minio-client.md`](operations/minio-client.md): inspecao e copia de
  objetos no MinIO.

## Referencia

- [`reference/ProjetoFinal_v2.pdf`](reference/ProjetoFinal_v2.pdf): enunciado
  oficial do projeto final (MBA).
