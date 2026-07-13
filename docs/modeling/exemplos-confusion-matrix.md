# Exemplos da Confusion Matrix

Este documento explica os quatro cenarios possiveis da matriz de confusao do
motor de decisao de credito. Os exemplos foram obtidos a partir do arquivo
`Dados/abt/abt_demo_holdout.parquet` e confirmados chamando a API `POST /score`
sem `features_override`.

No holdout de demonstracao atual:

- `TARGET = 0`: cliente adimplente no historico.
- `TARGET = 1`: cliente inadimplente no historico.
- `prediction = 0`: modelo aprovou o cliente.
- `prediction = 1`: modelo reprovou o cliente.
- `threshold = 8%`: acima ou igual a esse corte, o cliente e classificado como
  inadimplente pelo motor.

Resumo da matriz no holdout de demonstracao:

| Cenario | prediction | TARGET | Quantidade |
| --- | ---: | ---: | ---: |
| Verdadeiro Negativo (TN) | 0 | 0 | 206 |
| Verdadeiro Positivo (TP) | 1 | 1 | 16 |
| Falso Negativo (FN) | 0 | 1 | 9 |
| Falso Positivo (FP) | 1 | 0 | 77 |

## Verdadeiro Negativo (TN)

**Exemplo:** `SK_ID_CURR = 139767`

Resultado da API:

| Campo | Valor |
| --- | --- |
| `TARGET` | `0` |
| `prediction` | `0` |
| `probability` | `4,53%` |
| `risk_band` | `Risco moderado` |
| `label` | `Aprovado (Pagador Saudável)` |

Storytelling: este cliente foi aprovado pelo modelo e, no historico real do
holdout, era de fato adimplente. Para a mesa de credito, este e o caso em que a
decisao funciona como esperado: o banco concede credito para alguem que manteve
os pagamentos em dia. Em termos de negocio, e uma oportunidade capturada sem
adicionar inadimplencia historica.

No dashboard, esse caso aparece como:

> **Acerto — Verdadeiro Negativo:** O modelo aprovou este cliente e, de fato,
> ele manteve os pagamentos em dia no historico do banco.

## Verdadeiro Positivo (TP)

**Exemplo:** `SK_ID_CURR = 271722`

Resultado da API:

| Campo | Valor |
| --- | --- |
| `TARGET` | `1` |
| `prediction` | `1` |
| `probability` | `10,57%` |
| `risk_band` | `Alto risco` |
| `label` | `Reprovado (Risco de Inadimplência)` |

Storytelling: este cliente foi reprovado pelo modelo e, no historico real do
holdout, realmente apresentou inadimplencia. Este e o acerto mais importante
para uma politica conservadora de risco: o motor identificou um cliente que
poderia gerar perda de credito e bloqueou a concessao.

No dashboard, esse caso aparece como:

> **Acerto — Verdadeiro Positivo:** O modelo reprovou este cliente e, de fato,
> ele apresentou inadimplencia no historico do banco.

## Falso Negativo (FN)

**Exemplo:** `SK_ID_CURR = 450206`

Resultado da API:

| Campo | Valor |
| --- | --- |
| `TARGET` | `1` |
| `prediction` | `0` |
| `probability` | `6,24%` |
| `risk_band` | `Risco moderado` |
| `label` | `Aprovado (Pagador Saudável)` |

Storytelling: este cliente foi aprovado pelo modelo, mas o historico real do
holdout mostra inadimplencia. Este e o erro mais critico para o banco: a mesa
teria concedido credito para alguem que, no registro historico, nao pagou como
esperado. Em avaliacao de risco, esse tipo de erro costuma pesar mais do que
um falso positivo, porque pode virar perda financeira direta.

No dashboard, esse caso aparece como:

> **Erro grave — Falso Negativo:** O modelo aprovou este cliente, mas ele deu
> calote no historico do banco.

## Falso Positivo (FP)

**Exemplo:** `SK_ID_CURR = 423870`

Resultado da API:

| Campo | Valor |
| --- | --- |
| `TARGET` | `0` |
| `prediction` | `1` |
| `probability` | `15,69%` |
| `risk_band` | `Alto risco` |
| `label` | `Reprovado (Risco de Inadimplência)` |

Storytelling: este cliente foi reprovado pelo modelo, mas o historico real do
holdout mostra que ele era adimplente. O banco evita uma perda que nao
aconteceria e deixa de fazer uma operacao possivelmente boa. Esse erro nao
gera calote direto, mas pode reduzir receita, conversao e relacionamento com
clientes bons.

No dashboard, esse caso aparece como:

> **Falso Alarme — Falso Positivo:** O modelo reprovou este cliente, mas ele
> teria pago em dia no historico do banco.

## Como Reproduzir

Com os servicos `api` e `streamlit` rodando:

```bash
docker compose exec -T streamlit python -c "import json, pandas as pd; from urllib.request import Request, urlopen; df = pd.read_parquet('/app/Dados/abt/abt_demo_holdout.parquet', columns=['SK_ID_CURR', 'TARGET']); rec = df.iloc[0]; payload = json.dumps({'client_id': int(rec.SK_ID_CURR), 'features_override': {}}).encode(); req = Request('http://api:8000/score', data=payload, method='POST', headers={'Content-Type': 'application/json'}); print(json.loads(urlopen(req).read().decode()))"
```

Para reconstruir a matriz completa, percorra todos os `SK_ID_CURR` do holdout,
chame `POST /score` para cada cliente e cruze `prediction` com `TARGET`.

## Observacao Sobre Simulacoes

Quando o usuario altera campos no dashboard antes de rodar a escoragem, a
auditoria compara uma decisao simulada contra o historico real do cliente no
holdout. Nesses casos, o painel exibe uma ressalva explicita para deixar claro
que houve alteracao nos campos antes da decisao.
