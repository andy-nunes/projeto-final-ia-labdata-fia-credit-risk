"""Utilidades para o dicionario de variaveis da analise de risco (ABT)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from html import escape
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from scripts.model_config import get_model_config

ROOT_DIR = Path(__file__).resolve().parents[1]
ABT_PATH = ROOT_DIR / "Dados" / "abt" / "abt_train.parquet"
RAW_DESCRIPTION_CANDIDATES: tuple[Path, ...] = (
    ROOT_DIR / "Dados" / "raw" / "HomeCredit_columns_description.csv",
    ROOT_DIR / "app" / "data" / "HomeCredit_columns_description.csv",
)


@dataclass(frozen=True)
class ColumnDescription:
    """Descricao oficial de uma coluna disponibilizada no pacote Kaggle."""

    table: str
    description: str
    special: str


# Nomes de negócio usados na mesa de crédito (labels da UI).
COLUMN_BUSINESS_NAMES: dict[str, str] = {
    "SK_ID_CURR": "Identificador do Cliente",
    "TARGET": "Variável Alvo",
    "AMT_CREDIT": "Valor Solicitado (R$)",
    "AMT_ANNUITY": "Valor da Parcela Mensal (R$)",
    "AMT_GOODS_PRICE": "Valor do Bem Financiado (R$)",
    "NAME_EDUCATION_TYPE": "Grau de Escolaridade",
    "NAME_INCOME_TYPE": "Tipo de Renda",
    "ORGANIZATION_TYPE": "Tipo de Organização / Setor",
    "OCCUPATION_TYPE": "Profissão / Ocupação",
    "EXT_SOURCE_1": "Score Externo 1 (Bureau)",
    "EXT_SOURCE_2": "Score Externo 2 (Bureau)",
    "EXT_SOURCE_3": "Score Externo 3 (Bureau)",
    "DAYS_BIRTH": "Dias de Vida (Idade)",
    "DAYS_EMPLOYED": "Tempo de Emprego (Dias)",
    "DAYS_ID_PUBLISH": "Dias desde Emissão do RG",
    "DAYS_REGISTRATION": "Dias desde Registro (Endereço)",
    "EXT_SOURCE_MEAN": "Média dos Scores Externos",
    "EXT_SOURCE_CNT": "Qtd. de Scores Externos Disponíveis",
    "FLAG_EMPLOYED": "Está Empregado? (1=Sim, 0=Não)",
    "DAYS_EMPLOYED_YEARS": "Tempo de Emprego (Anos)",
    "BUREAU_AMT_DEBT_SUM": "Dívida Total em Outros Bancos (R$)",
    "BUREAU_DAYS_CREDIT_MIN": "Dias desde o 1º Crédito",
    "PREV_DAYS_DECISION_MIN": "Dias desde a Últ. Proposta",
    "INST_DIAS_ATRASO_MEAN": "Média de Dias em Atraso (Histórico)",
    "INST_AMT_PAYMENT_SUM": "Total Pago em Empréstimos Ant. (R$)",
    "INST_PAYMENT_RATIO": "Taxa de Pagamento de Parcelas",
    "INST_RATE_ATRASO": "Taxa de Atraso em Parcelas",
    "CODE_GENDER": "Gênero",
    "FLAG_OWN_CAR": "Possui Carro?",
    "OWN_CAR_AGE": "Idade do Veículo Próprio (Anos)",
    "FLAG_OWN_REALTY": "Possui Imóvel?",
    "CNT_CHILDREN": "Qtd. de Filhos",
    "CNT_FAM_MEMBERS": "Tamanho da Família",
    "AMT_INCOME_TOTAL": "Renda Total Declarada (R$)",
    "NAME_FAMILY_STATUS": "Estado Civil",
    "NAME_HOUSING_TYPE": "Tipo de Moradia",
    "AGE_YEARS": "Idade (Anos)",
    "CREDIT_INCOME_RATIO": "Comprometimento de Renda",
    "ANNUITY_INCOME_RATIO": "Comprometimento da Renda (Parcela/Renda)",
    "HAS_BUREAU": "Possui Histórico no Bureau?",
    "HAS_PREVIOUS_APP": "Possui Proposta Anterior?",
    "REGION_RATING_CLIENT": "Risco Regional do Cliente",
    "REGION_RATING_CLIENT_W_CITY": "Risco Regional (com Cidade)",
    "DEF_30_CNT_SOCIAL_CIRCLE": "Inadimplência na Rede Social (30d)",
    "OBS_30_CNT_SOCIAL_CIRCLE": "Consultas na Rede Social (30d)",
    "DEF_60_CNT_SOCIAL_CIRCLE": "Inadimplência na Rede Social (60d)",
    "OBS_60_CNT_SOCIAL_CIRCLE": "Consultas na Rede Social (60d)",
    "HOUR_APPR_PROCESS_START": "Hora da Solicitação de Crédito",
    "WEEKDAY_APPR_PROCESS_START": "Dia da Semana da Solicitação",
    "FLAG_DOCUMENT_3": "Forneceu Documento Principal (RG/CPF)",
    "LIVE_CITY_NOT_WORK_CITY": "Mora e Trabalha em Cidades Diferentes",
    "REG_CITY_NOT_LIVE_CITY": "Endereço Registrado Difere da Moradia",
    "CC_UTILIZATION_MEAN": "Média de Uso do Cartão de Crédito",
    "CC_AMT_BALANCE_MEAN": "Média de Saldo no Cartão de Crédito",
    "POS_CNT_MONTHS": "Meses em Financiamentos (POS)",
    "PREV_CNT_APPS": "Qtd. de Solicitações Anteriores",
    "PREV_CNT_APPROVED": "Qtd. de Solicitações Aprovadas Anteriores",
    "PREV_CNT_REFUSED": "Qtd. de Solicitações Reprovadas Anteriores",
}

HIGHLIGHT_COLUMNS: tuple[str, ...] = ("SK_ID_CURR", "TARGET")

HIGHLIGHT_ROLES: dict[str, str] = {
    "SK_ID_CURR": "Identificador",
    "TARGET": "Variável Alvo",
}

PREFIX_SOURCES: tuple[tuple[str, str], ...] = (
    ("BUREAU_", "bureau.csv"),
    ("BB_", "bureau_balance.csv"),
    ("POS_", "POS_CASH_balance.csv"),
    ("CC_", "credit_card_balance.csv"),
    ("PREV_", "previous_application.csv"),
    ("INST_", "installments_payments.csv"),
    ("HAS_", "features Gold"),
)

CATALOG_DISPLAY_LABELS: dict[str, str] = {
    "posicao": "Posição",
    "nome": "Nome",
    "tipo": "Tipo",
    "categoria": "Categoria",
    "fonte": "Fonte",
    "descricao": "Descrição",
    "especial": "Especial",
    "entra_no_modelo": "Modelo",
    "editavel_ui": "Editável",
    "categorica_modelo": "Categórica",
}

BUSINESS_DESCRIPTIONS: dict[str, str] = {
    "AGE_YEARS": "Idade do cliente em anos completos, calculada a partir da data de nascimento.",
    "AMT_ANNUITY": "Valor da parcela (anuidade) do crédito solicitado.",
    "AMT_CREDIT": "Valor total do crédito solicitado nesta proposta.",
    "AMT_GOODS_PRICE": "Preço do bem financiado na operação de crédito ao consumidor.",
    "AMT_INCOME_TOTAL": "Renda total declarada pelo cliente na proposta.",
    "AMT_REQ_CREDIT_BUREAU_DAY": "Quantidade de consultas ao Bureau de Crédito sobre o cliente no dia anterior à solicitação (excluindo a última hora).",
    "AMT_REQ_CREDIT_BUREAU_HOUR": "Quantidade de consultas ao Bureau de Crédito sobre o cliente na hora anterior à solicitação.",
    "AMT_REQ_CREDIT_BUREAU_MON": "Quantidade de consultas ao Bureau de Crédito sobre o cliente no mês anterior à solicitação (excluindo a última semana).",
    "AMT_REQ_CREDIT_BUREAU_QRT": "Quantidade de consultas ao Bureau de Crédito sobre o cliente nos 3 meses anteriores à solicitação (excluindo o último mês).",
    "AMT_REQ_CREDIT_BUREAU_WEEK": "Quantidade de consultas ao Bureau de Crédito sobre o cliente na semana anterior à solicitação (excluindo o último dia).",
    "AMT_REQ_CREDIT_BUREAU_YEAR": "Quantidade de consultas ao Bureau de Crédito sobre o cliente no último ano (excluindo os últimos 3 meses).",
    "ANNUITY_INCOME_RATIO": "Razão entre a parcela mensal e a renda total declarada (comprometimento de renda pela anuidade).",
    "APARTMENTS_AVG": "Informação normalizada sobre área de apartamentos do imóvel de moradia do cliente (média).",
    "APARTMENTS_MEDI": "Informação normalizada sobre área de apartamentos do imóvel de moradia do cliente (mediana).",
    "APARTMENTS_MODE": "Informação normalizada sobre área de apartamentos do imóvel de moradia do cliente (moda).",
    "BASEMENTAREA_AVG": "Informação normalizada sobre área de porão do imóvel de moradia do cliente (média).",
    "BASEMENTAREA_MEDI": "Informação normalizada sobre área de porão do imóvel de moradia do cliente (mediana).",
    "BASEMENTAREA_MODE": "Informação normalizada sobre área de porão do imóvel de moradia do cliente (moda).",
    "BB_CNT_CLOSED": "Quantidade de meses com status de contrato encerrado no histórico mensal do Bureau.",
    "BB_CNT_MONTHS": "Quantidade total de meses de histórico mensal dos contratos do Bureau (bureau balance).",
    "BB_CNT_OVERDUE": "Quantidade de meses com status de atraso no histórico mensal do Bureau.",
    "BB_CNT_UNKNOWN": "Quantidade de meses com status desconhecido no histórico mensal do Bureau.",
    "BB_CONTRACTS_WITH_OVERDUE": "Quantidade de contratos do Bureau que apresentaram ao menos um mês em atraso.",
    "BB_RATE_OVERDUE_MAX": "Maior taxa mensal de atraso entre os contratos do Bureau do cliente.",
    "BB_RATE_OVERDUE_MEAN": "Taxa média mensal de atraso nos contratos do Bureau do cliente.",
    "BUREAU_AMT_CREDIT_SUM_MAX": "Maior valor de crédito entre os contratos do cliente no Bureau.",
    "BUREAU_AMT_CREDIT_SUM_MEAN": "Valor médio de crédito dos contratos do cliente no Bureau.",
    "BUREAU_AMT_CREDIT_SUM_SUM": "Soma dos valores de crédito de todos os contratos do cliente no Bureau.",
    "BUREAU_AMT_DEBT_SUM": "Soma total das dívidas ativas e encerradas do cliente registradas no Bureau de Crédito.",
    "BUREAU_AMT_OVERDUE_MAX": "Maior valor em atraso observado nos contratos do cliente no Bureau.",
    "BUREAU_AMT_OVERDUE_SUM": "Soma dos valores em atraso dos contratos do cliente no Bureau.",
    "BUREAU_CNT_ACTIVE": "Quantidade de contratos ativos do cliente no Bureau de Crédito.",
    "BUREAU_CNT_BAD_DEBT": "Quantidade de contratos classificados como má dívida (bad debt) no Bureau.",
    "BUREAU_CNT_CLOSED": "Quantidade de contratos encerrados do cliente no Bureau de Crédito.",
    "BUREAU_CNT_CREDITS": "Quantidade total de contratos de crédito do cliente registrados no Bureau.",
    "BUREAU_CREDIT_DAY_OVERDUE_MAX": "Maior quantidade de dias em atraso registrada nos contratos do Bureau.",
    "BUREAU_DAYS_CREDIT_MIN": "Antiguidade do relacionamento de crédito no Bureau (dias desde o contrato mais antigo até a solicitação).",
    "CC_AMT_BALANCE_MAX": "Maior saldo utilizado no cartão de crédito do cliente.",
    "CC_AMT_BALANCE_MEAN": "Saldo médio utilizado no cartão de crédito do cliente.",
    "CC_AMT_LIMIT_MEAN": "Limite médio de crédito do cartão ao longo do histórico.",
    "CC_CNT_DPD_GT0": "Quantidade de meses com atraso superior a zero no cartão de crédito.",
    "CC_CNT_DRAWINGS_ATM_SUM": "Soma da quantidade de saques em ATM no cartão de crédito.",
    "CC_CNT_MONTHS": "Quantidade de meses de histórico de cartão de crédito do cliente.",
    "CC_RATE_DPD": "Proporção de meses com atraso no histórico de cartão de crédito.",
    "CC_SK_DPD_MAX": "Maior atraso (dias) observado no cartão de crédito do cliente.",
    "CC_SK_DPD_MEAN": "Atraso médio (dias) no histórico de cartão de crédito.",
    "CC_UTILIZATION_MAX": "Maior utilização do limite do cartão observada no histórico.",
    "CC_UTILIZATION_MEAN": "Utilização média do limite do cartão (saldo / limite).",
    "CNT_CHILDREN": "Quantidade de filhos declarada pelo cliente.",
    "CNT_FAM_MEMBERS": "Quantidade de membros na família do cliente.",
    "CODE_GENDER": "Sexo do cliente informado no cadastro da proposta.",
    "COMMONAREA_AVG": "Informação normalizada sobre área comum do imóvel de moradia do cliente (média).",
    "COMMONAREA_MEDI": "Informação normalizada sobre área comum do imóvel de moradia do cliente (mediana).",
    "COMMONAREA_MODE": "Informação normalizada sobre área comum do imóvel de moradia do cliente (moda).",
    "CREDIT_INCOME_RATIO": "Razão entre o valor do crédito solicitado e a renda total declarada (comprometimento de renda pelo principal).",
    "DAYS_BIRTH": "Idade do cliente em dias na data da solicitação (valores negativos relativos à data da proposta).",
    "DAYS_EMPLOYED": "Tempo de emprego atual em dias antes da solicitação (valores negativos relativos à data da proposta).",
    "DAYS_EMPLOYED_YEARS": "Tempo de emprego atual convertido para anos (módulo de DAYS_EMPLOYED / 365,25).",
    "DAYS_ID_PUBLISH": "Dias decorridos desde a emissão/alteração do documento de identidade usado na proposta.",
    "DAYS_LAST_PHONE_CHANGE": "Dias decorridos desde a última troca de telefone do cliente até a solicitação.",
    "DAYS_REGISTRATION": "Dias decorridos desde a última alteração cadastral do cliente até a solicitação.",
    "DEF_30_CNT_SOCIAL_CIRCLE": "Quantidade de pessoas do círculo social do cliente com inadimplência acima de 30 dias.",
    "DEF_60_CNT_SOCIAL_CIRCLE": "Quantidade de pessoas do círculo social do cliente com inadimplência acima de 60 dias.",
    "ELEVATORS_AVG": "Informação normalizada sobre quantidade de elevadores do prédio do cliente (média).",
    "ELEVATORS_MEDI": "Informação normalizada sobre quantidade de elevadores do prédio do cliente (mediana).",
    "ELEVATORS_MODE": "Informação normalizada sobre quantidade de elevadores do prédio do cliente (moda).",
    "EMERGENCYSTATE_MODE": "Indica se o imóvel de moradia está em situação de emergência (valor modal).",
    "ENTRANCES_AVG": "Informação normalizada sobre quantidade de entradas do prédio do cliente (média).",
    "ENTRANCES_MEDI": "Informação normalizada sobre quantidade de entradas do prédio do cliente (mediana).",
    "ENTRANCES_MODE": "Informação normalizada sobre quantidade de entradas do prédio do cliente (moda).",
    "EXT_SOURCE_1": "Score normalizado de fonte externa de crédito (fonte 1).",
    "EXT_SOURCE_2": "Score normalizado de fonte externa de crédito (fonte 2).",
    "EXT_SOURCE_3": "Score normalizado de fonte externa de crédito (fonte 3).",
    "EXT_SOURCE_CNT": "Quantidade de scores externos preenchidos para o cliente (de 0 a 3).",
    "EXT_SOURCE_MEAN": "Média dos scores externos disponíveis (EXT_SOURCE_1, EXT_SOURCE_2 e EXT_SOURCE_3).",
    "FLAG_CONT_MOBILE": "Indica se o telefone celular informado estava alcançável (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_10": "Indica se o cliente apresentou o documento 10 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_11": "Indica se o cliente apresentou o documento 11 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_12": "Indica se o cliente apresentou o documento 12 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_13": "Indica se o cliente apresentou o documento 13 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_14": "Indica se o cliente apresentou o documento 14 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_15": "Indica se o cliente apresentou o documento 15 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_16": "Indica se o cliente apresentou o documento 16 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_17": "Indica se o cliente apresentou o documento 17 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_18": "Indica se o cliente apresentou o documento 18 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_19": "Indica se o cliente apresentou o documento 19 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_2": "Indica se o cliente apresentou o documento 2 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_20": "Indica se o cliente apresentou o documento 20 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_21": "Indica se o cliente apresentou o documento 21 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_3": "Indica se o cliente apresentou o documento principal (RG/CPF) no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_4": "Indica se o cliente apresentou o documento 4 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_5": "Indica se o cliente apresentou o documento 5 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_6": "Indica se o cliente apresentou o documento 6 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_7": "Indica se o cliente apresentou o documento 7 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_8": "Indica se o cliente apresentou o documento 8 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_DOCUMENT_9": "Indica se o cliente apresentou o documento 9 exigido no processo de crédito (1 = sim, 0 = não).",
    "FLAG_EMAIL": "Indica se o cliente informou endereço de e-mail (1 = sim, 0 = não).",
    "FLAG_EMPLOYED": "Indicador de vínculo empregatício ativo (1 = empregado, 0 = sem emprego / marcador de desemprego tratado).",
    "FLAG_EMP_PHONE": "Indica se o cliente informou telefone comercial/do empregador (1 = sim, 0 = não).",
    "FLAG_EXT_SOURCE_1_MISSING": "Indica ausência do score externo 1 no dossiê do cliente.",
    "FLAG_EXT_SOURCE_2_MISSING": "Indica ausência do score externo 2 no dossiê do cliente.",
    "FLAG_EXT_SOURCE_3_MISSING": "Indica ausência do score externo 3 no dossiê do cliente.",
    "FLAG_MOBIL": "Indica se o cliente informou telefone celular (1 = sim, 0 = não).",
    "FLAG_OWN_CAR": "Indica se o cliente possui veículo próprio (Sim/Não).",
    "FLAG_OWN_REALTY": "Indica se o cliente possui imóvel próprio (casa ou apartamento).",
    "FLAG_PHONE": "Indica se o cliente informou telefone fixo (1 = sim, 0 = não).",
    "FLAG_WORK_PHONE": "Indica se o cliente informou telefone residencial/de trabalho (1 = sim, 0 = não).",
    "FLOORSMAX_AVG": "Informação normalizada sobre andar máximo do prédio do cliente (média).",
    "FLOORSMAX_MEDI": "Informação normalizada sobre andar máximo do prédio do cliente (mediana).",
    "FLOORSMAX_MODE": "Informação normalizada sobre andar máximo do prédio do cliente (moda).",
    "FLOORSMIN_AVG": "Informação normalizada sobre andar mínimo do prédio do cliente (média).",
    "FLOORSMIN_MEDI": "Informação normalizada sobre andar mínimo do prédio do cliente (mediana).",
    "FLOORSMIN_MODE": "Informação normalizada sobre andar mínimo do prédio do cliente (moda).",
    "FONDKAPREMONT_MODE": "Modalidade de fundo de reparo/manutenção do imóvel de moradia do cliente (valor modal).",
    "HAS_BUREAU": "Indica se o cliente possui histórico de contratos no Bureau de Crédito (1 = sim, 0 = não).",
    "HAS_BUREAU_BALANCE": "Indica se o cliente possui histórico mensal (bureau balance) disponível (1 = sim, 0 = não).",
    "HAS_CREDIT_CARD": "Indica se o cliente possui histórico de cartão de crédito (1 = sim, 0 = não).",
    "HAS_INSTALLMENTS": "Indica se o cliente possui histórico de pagamento de parcelas (1 = sim, 0 = não).",
    "HAS_POS_CASH": "Indica se o cliente possui histórico de financiamentos POS/CASH (1 = sim, 0 = não).",
    "HAS_PREVIOUS_APP": "Indica se o cliente possui proposta anterior na Home Credit (1 = sim, 0 = não).",
    "HOUR_APPR_PROCESS_START": "Hora aproximada em que a solicitação de crédito foi protocolada.",
    "HOUSETYPE_MODE": "Tipo de imóvel de moradia do cliente (valor modal).",
    "INST_AMT_GAP_SUM": "Soma das diferenças entre valor previsto e valor pago (pagamentos parciais).",
    "INST_AMT_INSTALMENT_SUM": "Soma dos valores previstos das parcelas de contratos anteriores.",
    "INST_AMT_PAYMENT_SUM": "Soma dos valores efetivamente pagos nas parcelas de contratos anteriores.",
    "INST_CNT_ATRASO": "Quantidade de parcelas pagas com atraso em contratos anteriores.",
    "INST_CNT_CALOTE": "Quantidade de parcelas sem qualquer pagamento (calote) em contratos anteriores.",
    "INST_CNT_PARCELAS": "Quantidade de parcelas históricas consolidadas de contratos anteriores.",
    "INST_CNT_UNDERPAY": "Quantidade de parcelas pagas abaixo do valor previsto em contratos anteriores.",
    "INST_DIAS_ATRASO_MAX": "Maior atraso (em dias) observado nas parcelas de contratos anteriores.",
    "INST_DIAS_ATRASO_MEAN": "Média de dias de atraso nas parcelas de contratos anteriores.",
    "INST_PAYMENT_RATIO": "Razão entre o total pago e o total previsto das parcelas anteriores.",
    "INST_RATE_ATRASO": "Proporção de parcelas anteriores pagas com atraso.",
    "INST_RATE_CALOTE": "Proporção de parcelas anteriores classificadas como calote (pagamento zero).",
    "INST_RATE_UNDERPAY": "Proporção de parcelas anteriores pagas abaixo do valor previsto.",
    "LANDAREA_AVG": "Informação normalizada sobre área do terreno do imóvel do cliente (média).",
    "LANDAREA_MEDI": "Informação normalizada sobre área do terreno do imóvel do cliente (mediana).",
    "LANDAREA_MODE": "Informação normalizada sobre área do terreno do imóvel do cliente (moda).",
    "LIVE_CITY_NOT_WORK_CITY": "Indica divergência entre endereço de contato e endereço de trabalho no nível de cidade.",
    "LIVE_REGION_NOT_WORK_REGION": "Indica divergência entre endereço de contato e endereço de trabalho no nível de região.",
    "LIVINGAPARTMENTS_AVG": "Informação normalizada sobre área habitável de apartamentos do cliente (média).",
    "LIVINGAPARTMENTS_MEDI": "Informação normalizada sobre área habitável de apartamentos do cliente (mediana).",
    "LIVINGAPARTMENTS_MODE": "Informação normalizada sobre área habitável de apartamentos do cliente (moda).",
    "LIVINGAREA_AVG": "Informação normalizada sobre área habitável do imóvel do cliente (média).",
    "LIVINGAREA_MEDI": "Informação normalizada sobre área habitável do imóvel do cliente (mediana).",
    "LIVINGAREA_MODE": "Informação normalizada sobre área habitável do imóvel do cliente (moda).",
    "LOG_AMT_CREDIT": "Transformação logarítmica (log1p) do valor do crédito solicitado, para estabilizar a escala da variável.",
    "NAME_CONTRACT_TYPE": "Modalidade do contrato solicitado (crédito em dinheiro ou crédito rotativo).",
    "NAME_EDUCATION_TYPE": "Maior grau de escolaridade alcançado pelo cliente.",
    "NAME_FAMILY_STATUS": "Estado civil / situação familiar do cliente.",
    "NAME_HOUSING_TYPE": "Situação de moradia do cliente (própria, alugada, com os pais etc.).",
    "NAME_INCOME_TYPE": "Tipo de renda do cliente (assalariado, empresário, licença-maternidade etc.).",
    "NAME_TYPE_SUITE": "Quem acompanhava o cliente no momento da solicitação do crédito.",
    "NONLIVINGAPARTMENTS_AVG": "Informação normalizada sobre área não habitável de apartamentos do cliente (média).",
    "NONLIVINGAPARTMENTS_MEDI": "Informação normalizada sobre área não habitável de apartamentos do cliente (mediana).",
    "NONLIVINGAPARTMENTS_MODE": "Informação normalizada sobre área não habitável de apartamentos do cliente (moda).",
    "NONLIVINGAREA_AVG": "Informação normalizada sobre área não habitável do imóvel do cliente (média).",
    "NONLIVINGAREA_MEDI": "Informação normalizada sobre área não habitável do imóvel do cliente (mediana).",
    "NONLIVINGAREA_MODE": "Informação normalizada sobre área não habitável do imóvel do cliente (moda).",
    "OBS_30_CNT_SOCIAL_CIRCLE": "Quantidade de observações do círculo social do cliente com referência a atraso observável acima de 30 dias.",
    "OBS_60_CNT_SOCIAL_CIRCLE": "Quantidade de observações do círculo social do cliente com referência a atraso observável acima de 60 dias.",
    "OCCUPATION_TYPE": "Profissão ou ocupação declarada pelo cliente.",
    "ORGANIZATION_TYPE": "Tipo de organização ou setor em que o cliente trabalha.",
    "OWN_CAR_AGE": "Idade do veículo próprio do cliente, em anos.",
    "POS_CNT_CONTRACTS": "Quantidade de contratos POS/CASH distintos no histórico do cliente.",
    "POS_CNT_DPD_GT0": "Quantidade de meses com atraso superior a zero no histórico POS/CASH.",
    "POS_CNT_MONTHS": "Quantidade de meses de histórico em financiamentos POS/CASH anteriores.",
    "POS_RATE_DPD": "Proporção de meses com atraso no histórico POS/CASH.",
    "POS_SK_DPD_MAX": "Maior atraso (dias) observado no histórico POS/CASH do cliente.",
    "POS_SK_DPD_MEAN": "Atraso médio (dias) no histórico POS/CASH do cliente.",
    "PREV_AMT_APPLICATION_MAX": "Maior valor solicitado entre as propostas anteriores.",
    "PREV_AMT_APPLICATION_MEAN": "Valor médio solicitado nas propostas anteriores.",
    "PREV_AMT_CREDIT_MEAN": "Valor médio de crédito concedido nas propostas anteriores.",
    "PREV_APPROVAL_RATE": "Taxa de aprovação das propostas anteriores (aprovadas / total).",
    "PREV_CNT_APPROVED": "Quantidade de propostas anteriores aprovadas.",
    "PREV_CNT_APPS": "Quantidade de propostas de crédito anteriores do cliente na Home Credit.",
    "PREV_CNT_CANCELED": "Quantidade de propostas anteriores canceladas.",
    "PREV_CNT_REFUSED": "Quantidade de propostas anteriores recusadas.",
    "PREV_DAYS_DECISION_MIN": "Dias desde a decisão da proposta anterior mais antiga (ou mais distante) até a solicitação atual.",
    "PREV_REFUSAL_RATE": "Taxa de recusa das propostas anteriores (recusadas / total).",
    "REGION_POPULATION_RELATIVE": "Densidade populacional normalizada da região de moradia; valores maiores indicam regiões mais populosas.",
    "REGION_RATING_CLIENT": "Classificação interna de risco da região onde o cliente mora (1, 2 ou 3).",
    "REGION_RATING_CLIENT_W_CITY": "Classificação interna de risco da região considerando também a cidade (1, 2 ou 3).",
    "REG_CITY_NOT_LIVE_CITY": "Indica divergência entre endereço permanente e endereço de contato no nível de cidade.",
    "REG_CITY_NOT_WORK_CITY": "Indica divergência entre endereço permanente e endereço de trabalho no nível de cidade.",
    "REG_REGION_NOT_LIVE_REGION": "Indica divergência entre endereço permanente e endereço de contato no nível de região.",
    "REG_REGION_NOT_WORK_REGION": "Indica divergência entre endereço permanente e endereço de trabalho no nível de região.",
    "SK_ID_CURR": "Código único de identificação do CPF/dossiê na base do Bureau.",
    "TARGET": "Indicador de inadimplência do cliente (0 = Adimplente / Parecer Favorável; 1 = Inadimplente / Calote).",
    "TOTALAREA_MODE": "Área total normalizada do imóvel de moradia do cliente (valor modal).",
    "WALLSMATERIAL_MODE": "Material predominante das paredes do imóvel de moradia (valor modal).",
    "WEEKDAY_APPR_PROCESS_START": "Dia da semana em que a solicitação de crédito foi protocolada.",
    "YEARS_BEGINEXPLUATATION_AVG": "Informação normalizada sobre anos desde o início da exploração do imóvel do cliente (média).",
    "YEARS_BEGINEXPLUATATION_MEDI": "Informação normalizada sobre anos desde o início da exploração do imóvel do cliente (mediana).",
    "YEARS_BEGINEXPLUATATION_MODE": "Informação normalizada sobre anos desde o início da exploração do imóvel do cliente (moda).",
    "YEARS_BUILD_AVG": "Informação normalizada sobre idade do prédio de moradia do cliente (média).",
    "YEARS_BUILD_MEDI": "Informação normalizada sobre idade do prédio de moradia do cliente (mediana).",
    "YEARS_BUILD_MODE": "Informação normalizada sobre idade do prédio de moradia do cliente (moda).",
}


DESCRIPTION_TRANSLATIONS: dict[str, str] = {
    "Age of client's car": "Idade do carro do cliente.",
    "Approximately at what hour did the client apply for the loan": "Hora aproximada em que o cliente solicitou o empréstimo.",
    "Client's age in days at the time of application": "Idade do cliente em dias no momento da solicitação.",
    "Clients income type (businessman, working, maternity leave,\x85)": "Tipo de renda do cliente, como empresário, empregado ou licença maternidade.",
    "Credit amount of the loan": "Valor do crédito solicitado.",
    "Did client provide email (1=YES, 0=NO)": "Indica se o cliente informou e-mail (1=sim, 0=não).",
    "Did client provide home phone (1=YES, 0=NO)": "Indica se o cliente informou telefone residencial (1=sim, 0=não).",
    "Did client provide mobile phone (1=YES, 0=NO)": "Indica se o cliente informou telefone celular (1=sim, 0=não).",
    "Did client provide work phone (1=YES, 0=NO)": "Indica se o cliente informou telefone comercial/de trabalho (1=sim, 0=não).",
    "Family status of the client": "Estado civil ou situação familiar do cliente.",
    "Flag if client owns a house or flat": "Indica se o cliente possui casa ou apartamento.",
    "Flag if client's contact address does not match work address (1=different, 0=same, at city level)": "Indica se o endereço de contato difere do endereço de trabalho, no nível de cidade (1=diferente, 0=igual).",
    "Flag if client's contact address does not match work address (1=different, 0=same, at region level)": "Indica se o endereço de contato difere do endereço de trabalho, no nível de região (1=diferente, 0=igual).",
    "Flag if client's permanent address does not match contact address (1=different, 0=same, at city level)": "Indica se o endereço permanente difere do endereço de contato, no nível de cidade (1=diferente, 0=igual).",
    "Flag if client's permanent address does not match contact address (1=different, 0=same, at region level)": "Indica se o endereço permanente difere do endereço de contato, no nível de região (1=diferente, 0=igual).",
    "Flag if client's permanent address does not match work address (1=different, 0=same, at city level)": "Indica se o endereço permanente difere do endereço de trabalho, no nível de cidade (1=diferente, 0=igual).",
    "Flag if client's permanent address does not match work address (1=different, 0=same, at region level)": "Indica se o endereço permanente difere do endereço de trabalho, no nível de região (1=diferente, 0=igual).",
    "Flag if the client owns a car": "Indica se o cliente possui carro.",
    "For consumer loans it is the price of the goods for which the loan is given": "Para crédito ao consumidor, representa o preço do bem financiado.",
    "Gender of the client": "Gênero do cliente.",
    "How many days before application did client change phone": "Quantidade de dias antes da solicitação em que o cliente alterou o telefone.",
    "How many days before the application did client change his registration": "Quantidade de dias antes da solicitação em que o cliente alterou seu cadastro.",
    "How many days before the application did client change the identity document with which he applied for the loan": "Quantidade de dias antes da solicitação em que o cliente alterou o documento de identidade usado no pedido.",
    "How many days before the application the person started current employment": "Quantidade de dias antes da solicitação em que o cliente iniciou o emprego atual.",
    "How many family members does client have": "Quantidade de membros na família do cliente.",
    "How many observation of client's social surroundings defaulted on 30 DPD (days past due)": "Quantidade de observações do círculo social do cliente com inadimplência acima de 30 dias.",
    "How many observation of client's social surroundings defaulted on 60 (days past due) DPD": "Quantidade de observações do círculo social do cliente com inadimplência acima de 60 dias.",
    "How many observation of client's social surroundings with observable 30 DPD (days past due) default": "Quantidade de observações do círculo social do cliente avaliáveis para inadimplência acima de 30 dias.",
    "How many observation of client's social surroundings with observable 60 DPD (days past due) default": "Quantidade de observações do círculo social do cliente avaliáveis para inadimplência acima de 60 dias.",
    "ID of loan in our sample": "Identificador do empréstimo/cliente na amostra.",
    "Identification if loan is cash or revolving": "Identifica se o empréstimo é em dinheiro ou crédito rotativo.",
    "Income of the client": "Renda total declarada pelo cliente.",
    "Level of highest education the client achieved": "Maior nível de escolaridade alcançado pelo cliente.",
    "Loan annuity": "Valor da parcela/anuidade do empréstimo.",
    "Normalized information about building where the client lives, What is average (_AVG suffix), modus (_MODE suffix), median (_MEDI suffix) apartment size, common area, living area, age of building, number of elevators, number of entrances, state of the building, number of floor": "Informação normalizada sobre o imóvel onde o cliente mora; os sufixos indicam média, moda ou mediana.",
    "Normalized population of region where client lives (higher number means the client lives in more populated region)": "População normalizada da região onde o cliente mora; valores maiores indicam regiões mais populosas.",
    "Normalized score from external data source": "Score normalizado de uma fonte externa de dados.",
    "Number of children the client has": "Quantidade de filhos do cliente.",
    "Number of enquiries to Credit Bureau about the client 3 month before application (excluding one month before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente nos 3 meses antes da solicitação, excluindo o último mês.",
    "Number of enquiries to Credit Bureau about the client one day before application (excluding one hour before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente no dia anterior à solicitação, excluindo a última hora.",
    "Number of enquiries to Credit Bureau about the client one day year (excluding last 3 months before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente no último ano, excluindo os últimos 3 meses antes da solicitação.",
    "Number of enquiries to Credit Bureau about the client one hour before application": "Quantidade de consultas ao bureau de crédito sobre o cliente na hora anterior à solicitação.",
    "Number of enquiries to Credit Bureau about the client one month before application (excluding one week before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente no mês anterior à solicitação, excluindo a última semana.",
    "Number of enquiries to Credit Bureau about the client one week before application (excluding one day before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente na semana anterior à solicitação, excluindo o último dia.",
    "On which day of the week did the client apply for the loan": "Dia da semana em que o cliente solicitou o empréstimo.",
    "Our rating of the region where client lives (1,2,3)": "Classificação interna da região onde o cliente mora (1, 2 ou 3).",
    "Our rating of the region where client lives with taking city into account (1,2,3)": "Classificação interna da região onde o cliente mora considerando também a cidade (1, 2 ou 3).",
    "Target variable (1 - client with payment difficulties: he/she had late payment more than X days on at least one of the first Y installments of the loan in our sample, 0 - all other cases)": "Indicador de inadimplência do cliente (0 = Adimplente / Parecer Favorável; 1 = Inadimplente / Calote).",
    "Type of organization where client works": "Tipo de organização ou setor onde o cliente trabalha.",
    "Was mobile phone reachable (1=YES, 0=NO)": "Indica se o telefone celular estava alcançável (1=sim, 0=não).",
    "What is the housing situation of the client (renting, living with parents, ...)": "Situação de moradia do cliente, como aluguel, casa própria ou morando com os pais.",
    "What kind of occupation does the client have": "Tipo de ocupação ou profissão do cliente.",
    "Who was accompanying client when he was applying for the loan": "Quem acompanhava o cliente no momento da solicitação do empréstimo.",
}

GENERIC_FORBIDDEN = "Feature criada na camada Gold a partir das tabelas limpas do projeto."


def resolve_description_path(
    path: Path | None = None,
) -> Path | None:
    """Retorna o primeiro CSV de descricao Kaggle disponivel."""
    if path is not None:
        return path if path.exists() else None
    for candidate in RAW_DESCRIPTION_CANDIDATES:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def _fallback_schema_from_business_descriptions() -> list[dict[str, str]]:
    """Schema minimo a partir do dicionario de negocio (198 colunas)."""
    rows: list[dict[str, str]] = []
    for name in sorted(BUSINESS_DESCRIPTIONS):
        if name in HIGHLIGHT_COLUMNS:
            data_type = "int64"
        elif name.startswith(("FLAG_", "HAS_")) or name.endswith("_CNT"):
            data_type = "int64"
        elif name.startswith("NAME_") or name in {
            "CODE_GENDER",
            "OCCUPATION_TYPE",
            "ORGANIZATION_TYPE",
            "WEEKDAY_APPR_PROCESS_START",
            "FONDKAPREMONT_MODE",
            "HOUSETYPE_MODE",
            "WALLSMATERIAL_MODE",
            "EMERGENCYSTATE_MODE",
        }:
            data_type = "string"
        else:
            data_type = "double"
        rows.append({"name": name, "type": data_type})
    return rows


def load_abt_schema(path: Path = ABT_PATH) -> list[dict[str, str]]:
    """Le o schema da ABT sem carregar o parquet completo em memoria."""
    try:
        if not path.exists() or path.stat().st_size == 0:
            return _fallback_schema_from_business_descriptions()
        schema = pq.read_schema(path)
        rows = [
            {"name": field.name, "type": str(field.type)}
            for field in schema
        ]
        if rows:
            return rows
    except Exception:
        pass
    return _fallback_schema_from_business_descriptions()


def load_kaggle_descriptions(
    path: Path | None = None,
) -> dict[str, ColumnDescription]:
    """Carrega descricoes oficiais do arquivo HomeCredit_columns_description."""
    resolved = resolve_description_path(path)
    if resolved is None:
        return {}

    frame = pd.read_csv(resolved, encoding="latin1")
    descriptions: dict[str, ColumnDescription] = {}

    for row in frame.itertuples(index=False):
        column_name = str(getattr(row, "Row")).strip()
        table = str(getattr(row, "Table")).strip()
        description = str(getattr(row, "Description")).strip()
        special = getattr(row, "Special")
        special_text = "" if pd.isna(special) else str(special).strip()

        current = descriptions.get(column_name)
        if current is None or "application_" in table:
            descriptions[column_name] = ColumnDescription(
                table=table,
                description=description,
                special=special_text,
            )

    return descriptions


def infer_source(column_name: str, official: ColumnDescription | None) -> str:
    """Infere a fonte operacional da coluna no catalogo."""
    if official is not None:
        return official.table
    for prefix, source in PREFIX_SOURCES:
        if column_name.startswith(prefix):
            return source
    if column_name in BUSINESS_DESCRIPTIONS:
        return "feature engineering Gold"
    return "feature engineering Gold"


def infer_category(column_name: str, official: ColumnDescription | None) -> str:
    """Classifica a coluna em um grupo operacional para filtragem."""
    if column_name == "SK_ID_CURR":
        return "Identificador"
    if column_name == "TARGET":
        return "Alvo"
    if column_name in {
        "AGE_YEARS",
        "FLAG_EMPLOYED",
        "EXT_SOURCE_MEAN",
        "EXT_SOURCE_CNT",
        "CREDIT_INCOME_RATIO",
        "ANNUITY_INCOME_RATIO",
        "LOG_AMT_CREDIT",
        "DAYS_EMPLOYED_YEARS",
    } or (
        column_name.startswith("FLAG_EXT_SOURCE_")
        and column_name.endswith("_MISSING")
    ):
        return "Derivada"
    if column_name.startswith(("FLAG_", "HAS_")):
        return "Indicador"
    if official is not None:
        return "Raw Kaggle"
    if any(column_name.startswith(prefix) for prefix, _ in PREFIX_SOURCES):
        return "Agregado"
    return "Derivada"


def _pattern_business_description(column_name: str) -> str:
    """Gera descricao executiva a partir do nome tecnico (fallback sem genericos)."""
    if column_name.startswith("FLAG_EXT_SOURCE_") and column_name.endswith("_MISSING"):
        source_name = column_name.removeprefix("FLAG_").removesuffix("_MISSING")
        return f"Indica ausência do score externo {source_name} no dossiê do cliente."

    if column_name.startswith("FLAG_DOCUMENT_"):
        number = column_name.removeprefix("FLAG_DOCUMENT_")
        return (
            f"Indica se o cliente apresentou o documento {number} "
            "exigido no processo de crédito (1 = sim, 0 = não)."
        )

    if column_name.startswith("HAS_"):
        topic = column_name.removeprefix("HAS_").replace("_", " ").lower()
        return f"Indica se o cliente possui histórico de {topic} (1 = sim, 0 = não)."

    prefix_labels = {
        "BUREAU_": "no Bureau de Crédito",
        "BB_": "no histórico mensal do Bureau",
        "POS_": "no histórico POS/CASH",
        "CC_": "no histórico de cartão de crédito",
        "PREV_": "nas propostas anteriores",
        "INST_": "no histórico de parcelas",
    }
    for prefix, context in prefix_labels.items():
        if column_name.startswith(prefix):
            metric = column_name[len(prefix):].replace("_", " ").lower()
            return f"Indicador agregado ({metric}) do cliente {context}."

    return (
        f"Variável da análise de risco utilizada pela mesa de crédito "
        f"({column_name})."
    )


def infer_description(column_name: str, official: ColumnDescription | None) -> str:
    """Retorna descricao de negocio priorizando dicionario interno e Kaggle."""
    curated = BUSINESS_DESCRIPTIONS.get(column_name)
    if curated:
        return curated

    if official is not None:
        translated = translate_description(official.description)
        if translated and translated != GENERIC_FORBIDDEN:
            return translated

    return _pattern_business_description(column_name)


def translate_description(description: str) -> str:
    """Traduz descricoes oficiais recorrentes para portugues."""
    document_match = re.fullmatch(r"Did client provide document (\d+)", description)
    if document_match:
        return (
            "Indica se o cliente apresentou o documento "
            f"{document_match.group(1)} "
            "exigido no processo de crédito (1 = sim, 0 = não)."
        )
    return DESCRIPTION_TRANSLATIONS.get(description, description)


def build_catalog_frame(
    schema_rows: list[dict[str, str]] | None = None,
    descriptions: dict[str, ColumnDescription] | None = None,
) -> pd.DataFrame:
    """Monta dataframe pesquisavel com metadados de todas as colunas da ABT."""
    config = get_model_config()
    schema = schema_rows if schema_rows is not None else load_abt_schema()
    official_descriptions = (
        descriptions if descriptions is not None else load_kaggle_descriptions()
    )
    drop_cols = set(config.drop_cols)
    editable = set(config.editable_features)
    categorical = set(config.categorical_features)

    records: list[dict[str, Any]] = []
    for position, field in enumerate(schema, start=1):
        column_name = field["name"]
        official = official_descriptions.get(column_name)
        description = infer_description(column_name, official)
        if description.strip() == GENERIC_FORBIDDEN:
            description = _pattern_business_description(column_name)
        records.append(
            {
                "posicao": position,
                "nome": column_name,
                "tipo": field["type"],
                "categoria": infer_category(column_name, official),
                "fonte": infer_source(column_name, official),
                "descricao": description,
                "especial": official.special if official else "",
                "entra_no_modelo": "Nao" if column_name in drop_cols else "Sim",
                "editavel_ui": "Sim" if column_name in editable else "Nao",
                "categorica_modelo": "Sim" if column_name in categorical else "Nao",
            }
        )

    return pd.DataFrame.from_records(records)


def filter_catalog(
    frame: pd.DataFrame,
    query: str = "",
    categories: list[str] | None = None,
    sources: list[str] | None = None,
) -> pd.DataFrame:
    """Filtra catalogo por texto livre, categoria e fonte."""
    filtered = frame.copy()

    if categories:
        filtered = filtered[filtered["categoria"].isin(categories)]

    if sources:
        filtered = filtered[filtered["fonte"].isin(sources)]

    normalized_query = query.strip().lower()
    if normalized_query:
        searchable = filtered[
            ["nome", "tipo", "categoria", "fonte", "descricao", "especial"]
        ].astype(str)
        mask = searchable.apply(
            lambda row: normalized_query in " ".join(row).lower(),
            axis=1,
        )
        filtered = filtered[mask]

    return filtered.reset_index(drop=True)


def render_catalog_table_html(frame: pd.DataFrame) -> str:
    """Renderiza catalogo em HTML simples para evitar crash do dataframe nativo."""
    if frame.empty:
        return (
            '<div class="catalog-empty">'
            "Nenhum campo encontrado para os filtros selecionados."
            "</div>"
        )

    display_columns = [
        column for column in CATALOG_DISPLAY_LABELS
        if column in frame.columns
    ]
    header_cells = "".join(
        f"<th>{escape(CATALOG_DISPLAY_LABELS[column])}</th>"
        for column in display_columns
    )

    body_rows: list[str] = []
    for row in frame[display_columns].itertuples(index=False, name=None):
        cells = "".join(
            f"<td>{escape('' if pd.isna(value) else str(value))}</td>"
            for value in row
        )
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        '<div class="catalog-table-wrap">'
        '<table class="catalog-table">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )


def render_catalog_explorer_html(frame: pd.DataFrame) -> str:
    """Renderiza explorador client-side para evitar rerender do Streamlit."""
    display_columns = [
        column for column in CATALOG_DISPLAY_LABELS
        if column in frame.columns
    ]
    labels = {column: CATALOG_DISPLAY_LABELS[column] for column in display_columns}
    records = (
        frame[display_columns]
        .fillna("")
        .astype(str)
        .to_dict(orient="records")
    )
    categories = sorted(frame["categoria"].dropna().astype(str).unique())
    sources = sorted(frame["fonte"].dropna().astype(str).unique())
    payload = json.dumps(
        {
            "columns": display_columns,
            "labels": labels,
            "records": records,
            "categories": categories,
            "sources": sources,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    :root {{
      color-scheme: dark;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    html, body {{
      background: #0e1117;
      color: #fafafa;
      margin: 0;
      padding: 0;
    }}
    .catalog-shell {{
      display: grid;
      gap: 0.9rem;
    }}
    .catalog-search-form,
    .filter-group {{
      border: 1px solid #273142;
      border-radius: 8px;
      padding: 0.75rem;
    }}
    .filter-label {{
      color: #cbd5e1;
      display: block;
      font-size: 0.82rem;
      font-weight: 700;
      margin-bottom: 0.55rem;
    }}
    .catalog-search-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }}
    #catalog-search {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      color: #f8fafc;
      flex: 1 1 280px;
      min-height: 2.45rem;
      padding: 0 0.75rem;
    }}
    #catalog-search:focus {{
      border-color: #60a5fa;
      outline: none;
    }}
    .catalog-button,
    .filter-chip {{
      border: 1px solid #334155;
      border-radius: 999px;
      color: #cbd5e1;
      cursor: pointer;
      display: inline-block;
      font-size: 0.78rem;
      font-weight: 700;
      line-height: 1;
      padding: 0.5rem 0.68rem;
      text-decoration: none;
    }}
    .catalog-button {{
      background: #2563eb;
      border-color: #3b82f6;
      border-radius: 8px;
      color: #fff;
      font-size: 0.84rem;
      min-height: 2.45rem;
      padding: 0.62rem 0.85rem;
    }}
    .filter-chip:hover,
    .catalog-button:hover {{
      background: rgba(59, 130, 246, 0.18);
      border-color: #60a5fa;
      color: #f8fafc;
    }}
    .filter-chip-active {{
      background: #2563eb;
      border-color: #3b82f6;
      color: #ffffff;
    }}
    .filter-chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.42rem;
    }}
    .catalog-summary {{
      color: #cbd5e1;
      font-size: 0.84rem;
    }}
    .catalog-table-wrap {{
      border: 1px solid #273142;
      border-radius: 8px;
      max-height: 56vh;
      overflow: auto;
      width: 100%;
    }}
    .catalog-table {{
      border-collapse: collapse;
      color: #e5e7eb;
      font-size: 0.82rem;
      min-width: 1180px;
      width: 100%;
    }}
    .catalog-table thead th {{
      background: #111827;
      border-bottom: 1px solid #334155;
      color: #f8fafc;
      font-weight: 700;
      position: sticky;
      text-align: left;
      top: 0;
      z-index: 1;
    }}
    .catalog-table th,
    .catalog-table td {{
      border-bottom: 1px solid #1f2937;
      line-height: 1.35;
      padding: 0.64rem 0.72rem;
      vertical-align: top;
    }}
    .catalog-table tbody tr:nth-child(even) {{
      background: rgba(30, 41, 59, 0.35);
    }}
    .catalog-table tbody tr:hover {{
      background: rgba(59, 130, 246, 0.14);
    }}
    .catalog-table td:nth-child(1),
    .catalog-table td:nth-child(3),
    .catalog-table td:nth-child(4),
    .catalog-table td:nth-child(8),
    .catalog-table td:nth-child(9),
    .catalog-table td:nth-child(10) {{
      white-space: nowrap;
    }}
    .catalog-empty {{
      border: 1px solid #273142;
      border-radius: 8px;
      color: #cbd5e1;
      padding: 1rem;
    }}
  </style>
</head>
<body>
  <div class="catalog-shell">
    <form class="catalog-search-form" id="search-form">
      <label class="filter-label" for="catalog-search">Pesquisar</label>
      <div class="catalog-search-row">
        <input id="catalog-search" type="search"
          placeholder="Ex.: AMT_CREDIT, bureau, parcela, score externo">
        <button class="catalog-button" type="submit">Pesquisar</button>
        <button class="catalog-button" id="clear-button" type="button">Limpar</button>
        <button class="catalog-button" id="download-button" type="button">
          Baixar catálogo em CSV
        </button>
      </div>
    </form>
    <div class="filter-group">
      <div class="filter-label">Categoria</div>
      <div class="filter-chip-row" id="category-filters"></div>
    </div>
    <div class="filter-group">
      <div class="filter-label">Fonte</div>
      <div class="filter-chip-row" id="source-filters"></div>
    </div>
    <div class="catalog-summary" id="catalog-summary"></div>
    <div id="catalog-table"></div>
  </div>
  <script>
    const catalogData = {payload};
    let selectedCategory = "";
    let selectedSource = "";
    let query = "";

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function matchesQuery(row) {{
      if (!query) {{
        return true;
      }}
      const text = catalogData.columns.map((column) => row[column]).join(" ").toLowerCase();
      return text.includes(query);
    }}

    function filteredRows() {{
      return catalogData.records.filter((row) => {{
        const categoryOk = !selectedCategory || row.categoria === selectedCategory;
        const sourceOk = !selectedSource || row.fonte === selectedSource;
        return categoryOk && sourceOk && matchesQuery(row);
      }});
    }}

    function renderChips(containerId, options, selectedValue, onClick) {{
      const container = document.getElementById(containerId);
      const allActive = selectedValue === "";
      const chips = [
        `<button type="button" class="filter-chip ${{allActive ? "filter-chip-active" : ""}}" data-value="">Todas</button>`
      ];
      for (const option of options) {{
        const active = selectedValue === option;
        const label = active ? `${{option}} ×` : option;
        chips.push(
          `<button type="button" class="filter-chip ${{active ? "filter-chip-active" : ""}}" data-value="${{escapeHtml(option)}}">${{escapeHtml(label)}}</button>`
        );
      }}
      container.innerHTML = chips.join("");
      container.querySelectorAll("button").forEach((button) => {{
        button.addEventListener("click", () => onClick(button.dataset.value || ""));
      }});
    }}

    function renderTable(rows) {{
      const target = document.getElementById("catalog-table");
      if (rows.length === 0) {{
        target.innerHTML = '<div class="catalog-empty">Nenhum campo encontrado para os filtros selecionados.</div>';
        return;
      }}
      const header = catalogData.columns
        .map((column) => `<th>${{escapeHtml(catalogData.labels[column])}}</th>`)
        .join("");
      const body = rows.map((row) => {{
        const cells = catalogData.columns
          .map((column) => `<td>${{escapeHtml(row[column])}}</td>`)
          .join("");
        return `<tr>${{cells}}</tr>`;
      }}).join("");
      target.innerHTML = `
        <div class="catalog-table-wrap">
          <table class="catalog-table">
            <thead><tr>${{header}}</tr></thead>
            <tbody>${{body}}</tbody>
          </table>
        </div>
      `;
    }}

    function applyFilters() {{
      query = document.getElementById("catalog-search").value.trim().toLowerCase();
      const rows = filteredRows();
      renderChips("category-filters", catalogData.categories, selectedCategory, (value) => {{
        selectedCategory = value === selectedCategory ? "" : value;
        applyFilters();
      }});
      renderChips("source-filters", catalogData.sources, selectedSource, (value) => {{
        selectedSource = value === selectedSource ? "" : value;
        applyFilters();
      }});
      document.getElementById("catalog-summary").textContent =
        `${{rows.length}} de ${{catalogData.records.length}} campos exibidos`;
      renderTable(rows);
    }}

    function downloadCsv() {{
      const rows = filteredRows();
      const header = catalogData.columns.map((column) => catalogData.labels[column]);
      const csvRows = [header, ...rows.map((row) => catalogData.columns.map((column) => row[column]))];
      const csv = csvRows.map((row) => row.map((value) => {{
        const text = String(value ?? "");
        return `"${{text.replaceAll('"', '""')}}"`;
      }}).join(",")).join("\\n");
      const blob = new Blob([csv], {{ type: "text/csv;charset=utf-8" }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "catalogo_abt.csv";
      link.click();
      URL.revokeObjectURL(url);
    }}

    document.getElementById("search-form").addEventListener("submit", (event) => {{
      event.preventDefault();
      applyFilters();
    }});
    document.getElementById("catalog-search").addEventListener("input", applyFilters);
    document.getElementById("clear-button").addEventListener("click", () => {{
      selectedCategory = "";
      selectedSource = "";
      document.getElementById("catalog-search").value = "";
      applyFilters();
    }});
    document.getElementById("download-button").addEventListener("click", downloadCsv);
    applyFilters();
  </script>
</body>
</html>
"""



def catalog_iframe_url() -> str:
    """URL do explorador HTML legado (mantido para a rota FastAPI `/catalog/abt`)."""
    import os

    base = os.getenv("API_BROWSER_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/catalog/abt"


def business_name(column_name: str) -> str:
    """Retorna o nome de negócio da variável, se houver tradução."""
    return COLUMN_BUSINESS_NAMES.get(column_name, column_name)


def format_variable_entry(
    *,
    column_name: str,
    data_type: str,
    description: str,
    role: str | None = None,
) -> str:
    """Formata uma variável no estilo textual do dicionário de risco."""
    type_token = f"{role} - {data_type}" if role else data_type
    desc = description.strip() or "Sem descrição disponível."
    return f"**{column_name}** *({type_token})*\n* {desc}"


@lru_cache(maxsize=1)
def _build_catalog_markdown_blocks() -> tuple[str, str]:
    """Monta e memoiza os blocos markdown do dicionário (highlight + demais)."""
    catalog = build_catalog_frame()
    by_name = {
        str(row["nome"]): row
        for row in catalog.to_dict(orient="records")
    }

    highlight_blocks: list[str] = []
    for column_name in HIGHLIGHT_COLUMNS:
        row = by_name.get(column_name)
        if row is None:
            continue
        highlight_blocks.append(
            format_variable_entry(
                column_name=column_name,
                data_type=str(row["tipo"]),
                description=str(row["descricao"]),
                role=HIGHLIGHT_ROLES.get(column_name),
            )
        )

    remaining = catalog[~catalog["nome"].isin(HIGHLIGHT_COLUMNS)].copy()
    remaining = remaining.sort_values("nome", kind="mergesort")
    entries = [
        format_variable_entry(
            column_name=str(row["nome"]),
            data_type=str(row["tipo"]),
            description=str(row["descricao"]),
        )
        for row in remaining.to_dict(orient="records")
    ]
    return "\n\n".join(highlight_blocks), "\n\n".join(entries)


def render_catalog(*, show_back_link: bool = False) -> None:
    """Renderiza o dicionário de variáveis de risco para a mesa de crédito.

    Lista contínua em Markdown puro: destaque de identificador/alvo e demais
    variáveis em fluxo único, sem tabelas, filtros ou blocos por categoria.
    """
    import streamlit as st

    st.markdown(
        """
        <style>
        div[data-testid="stMarkdown"] p {
            margin-bottom: 0.35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Variáveis da Análise de Risco")
    st.caption(
        "Abaixo estão listados e explicados os fatores e determinantes "
        "utilizados pelo motor de decisão de crédito."
    )

    if show_back_link:
        st.caption("Navegação disponível pela aba superior da Mesa de Crédito.")

    highlight_md, remaining_md = _build_catalog_markdown_blocks()
    if highlight_md:
        st.markdown(highlight_md)
    if remaining_md:
        st.markdown(remaining_md)
