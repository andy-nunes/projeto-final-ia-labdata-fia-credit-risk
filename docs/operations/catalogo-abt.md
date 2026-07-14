# Dicionario de Variaveis da ABT no Streamlit

## Objetivo

O dicionario de variaveis da ABT documenta, dentro do Streamlit, todas as
colunas da tabela analitica final usada pelo modelo LightGBM. Ele e acessado
pela aba **Dicionário de Variáveis** em `app/dashboard.py` (modulo
`app/abt_catalog.py`).

A tela permite consultar:

- nome da coluna;
- tipo no Parquet;
- categoria operacional;
- fonte de origem;
- descricao em portugues;
- marcacao de coluna especial do Kaggle;
- se entra no modelo;
- se e editavel na UI;
- se e categorica para o modelo.

## Fontes De Metadados

A montagem do dicionario fica em `app/abt_catalog.py` e combina tres fontes:

1. Schema de `Dados/abt/abt_train.parquet`, lido com `pyarrow` sem carregar o
   Parquet inteiro em memoria.
2. Configuracao de `Model/model_config.yaml`, usada para marcar colunas fora
   do modelo, features editaveis e features categoricas.
3. Dicionario oficial `Dados/raw/HomeCredit_columns_description.csv`,
   distribuido no pacote de dados da competicao Home Credit Default Risk no
   Kaggle.

As features criadas na camada Gold recebem descricao inferida pela regra de
engenharia ou pelo prefixo da fonte agregada (`BUREAU_`, `BB_`, `POS_`, `CC_`,
`PREV_`, `INST_` e `HAS_`).

## Descricoes Em Portugues

As descricoes oficiais do Kaggle estao em ingles. Antes de montar o dataframe
do dicionario, `app/abt_catalog.py` aplica `translate_description`, que traduz os
textos recorrentes para portugues.

Tambem ha uma regra para as flags documentais:

```text
Did client provide document N -> Indica se o cliente apresentou o documento N.
```

As descricoes derivadas e agregadas ja sao mantidas em portugues no proprio
codigo do dicionario. Se novas colunas raw entrarem na ABT e aparecerem com
descricao em ingles, atualize `DESCRIPTION_TRANSLATIONS` em
`app/abt_catalog.py`.

## Arquitetura Da Tela

A pagina do dicionario usa metricas simples do Streamlit, mas a experiencia
pesquisavel roda em um componente HTML/JavaScript client-side gerado por
`render_catalog_explorer_html`.

Essa decisao e intencional. Durante os testes manuais, widgets interativos do
Streamlit no dicionario (`st.dataframe`, `st.multiselect`, `st.selectbox`,
`st.text_input` e `st.download_button`) provocaram crashes nativos do processo
com status `Exited (139)` em rerenders sucessivos. Por isso, busca, filtros,
tabela e download CSV nao devem voltar a usar esses widgets nessa pagina.

O componente client-side:

- carrega todos os registros do dicionario uma vez;
- filtra por texto no navegador;
- filtra por categoria e fonte sem rerenderizar o Streamlit;
- permite remover filtros clicando novamente no chip ativo;
- baixa CSV com o resultado filtrado no navegador.

## Colunas Fora Do Modelo

A ABT atual possui 198 colunas. O modelo usa 196 features. As duas colunas
fora do modelo sao:

- `SK_ID_CURR`: identificador do cliente;
- `TARGET`: variavel alvo historica.

Ambas aparecem no catalogo, mas com `entra_no_modelo = Nao`.

## Validacao

Ao alterar `app/abt_catalog.py`, `app/dashboard.py` ou metadados de
features, rode:

```bash
docker compose run --rm streamlit python -m pytest /app/tests/test_abt_catalog.py /app/tests/test_dashboard_layout.py -q
docker compose run --rm streamlit python -m py_compile /app/app/abt_catalog.py /app/app/dashboard.py
```

Para validar o servico em execucao:

```bash
docker compose up -d streamlit
curl -sS -I http://localhost:8501/
docker compose ps streamlit
```

O esperado e HTTP `200 OK` e o container `streamlit` em estado `Up`.
