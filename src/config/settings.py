from __future__ import annotations

import os
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# helpers de leitura de env
# ---------------------------------------------------------------------------

def _get_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key, str(default)).strip().lower()
    return raw in ("1", "true", "yes")


def _mask_token(token: str) -> str:
    if not token:
        return "(vazio)"
    if len(token) <= 8:
        return "****"
    return token[:4] + "****" + token[-4:]


# ---------------------------------------------------------------------------
# credenciais / API
# ---------------------------------------------------------------------------

TOKEN_MONDAY: str = _get_str("MONDAY_API_TOKEN")
API_URL: str = _get_str("MONDAY_BASE_URL", "https://api.monday.com/v2")
HEADERS: Dict[str, str] = {
    "Authorization": TOKEN_MONDAY,
    "Content-Type": "application/json",
}

LOG_PREFIX: str = _get_str("PIPELINE_LOG_PREFIX", "[AL-RH]")
SHOW_PROGRESS: bool = _get_bool("PIPELINE_SHOW_PROGRESS", True)

# ---------------------------------------------------------------------------
# retry / backoff / paginação
# ---------------------------------------------------------------------------

MAX_RETRIES: int = _get_int("MONDAY_MAX_RETRIES", 5)
REQUEST_TIMEOUT: int = _get_int("MONDAY_REQUEST_TIMEOUT", 60)
BASE_DELAY: float = _get_float("MONDAY_BACKOFF_BASE", 1.0)
BACKOFF_FACTOR: float = _get_float("MONDAY_BACKOFF_FACTOR", 2.0)
MAX_DELAY: float = _get_float("MONDAY_BACKOFF_CAP", 30.0)
JITTER_MIN: float = _get_float("MONDAY_JITTER_MIN", 0.0)
JITTER_MAX: float = _get_float("MONDAY_JITTER_MAX", 0.5)
PAGE_LIMIT: int = _get_int("MONDAY_PAGE_LIMIT", 500)

# ---------------------------------------------------------------------------
# sleeps
# ---------------------------------------------------------------------------

CREATE_SLEEP_SECONDS: float = _get_float("MONDAY_CREATE_SLEEP_SECONDS", 0.15)
ACTION_SLEEP_SECONDS: float = _get_float("MONDAY_ACTION_SLEEP_SECONDS", 0.15)

# ---------------------------------------------------------------------------
# dry-runs
# ---------------------------------------------------------------------------

CREATE_DRY_RUN: bool = _get_bool("PIPELINE_CREATE_DRY_RUN", False)
DELETE_DUPLICATE_DRY_RUN: bool = _get_bool("PIPELINE_DELETE_DUPLICATE_DRY_RUN", False)
DELETE_WRONG_BOARD_DRY_RUN: bool = _get_bool("PIPELINE_DELETE_WRONG_BOARD_DRY_RUN", False)
DELETE_NO_ORIGIN_DRY_RUN: bool = _get_bool("PIPELINE_DELETE_NO_ORIGIN_DRY_RUN", False)
UPDATE_CRITICAL_DRY_RUN: bool = _get_bool("PIPELINE_UPDATE_CRITICAL_DRY_RUN", False)
MOVE_WRONG_GROUPS_DRY_RUN: bool = _get_bool("PIPELINE_MOVE_WRONG_GROUPS_DRY_RUN", False)

# ---------------------------------------------------------------------------
# boards de origem RH (escalável por ano — adicione novo dict para 2027+)
# ---------------------------------------------------------------------------

ORIGIN_BOARDS: List[Dict[str, Any]] = [
    {
        "year": 2025,
        "board_id": "18391688378",
        "board_name": "BASE MENSAL 2025",
        "grupo_base_id": "group_mm12wsw3",
        "grupo_desligados_id": "group_mm12p1ah",
    },
    {
        "year": 2026,
        "board_id": "18402103538",
        "board_name": "BASE MENSAL 2026",
        "grupo_base_id": "group_mm12ejfg",
        "grupo_desligados_id": "group_mm12p1ah",
    },
]

# ---------------------------------------------------------------------------
# IDs de colunas críticas
# ---------------------------------------------------------------------------

COL_DEPARTAMENTO: str = "dropdown_mkygtfxa"
COL_DEST_ORIGIN_ITEM_ID: str = "text_mm31mj51"
COL_MOTIVO_DESLIGAMENTO_ORIGEM: str = "dropdown_mm11en3g"
COL_MOTIVO_DESLIGAMENTO_DESTINO: str = "color_mkykbpd9"
COL_TIPO_DESLIGAMENTO: str = "dropdown_mkygzk0c"
COL_SALARIO_BASE: str = "numeric_mkyg7gcz"
COL_SALARIO_BRUTO: str = "numeric_mkygc35k"
COL_VALOR_LIQUIDO: str = "numeric_mkyg4sxh"

# ---------------------------------------------------------------------------
# boards de destino (5 empresas)
# ---------------------------------------------------------------------------

DESTINATIONS: Dict[str, Dict[str, Any]] = {
    "ENEVA": {
        "board_id": "18411983294",
        "board_name": "[Py] ENEVA - RH",
        "grupo_base_id": "topics",
        "grupo_desligados_id": "group_mkykx7wz",
        "dept_keywords": ["ENEVA"],
    },
    "FS_BIO_CPT01": {
        "board_id": "18411734941",
        "board_name": "[Py] FS Bio & CPT01 - RH",
        "grupo_base_id": "topics",
        "grupo_desligados_id": "group_mkykx7wz",
        "dept_keywords": ["FS INDUSTRIA", "PERFURACAO"],
    },
    "SPTS": {
        "board_id": "18411984660",
        "board_name": "[Py] SPTs - RH",
        "grupo_base_id": "topics",
        "grupo_desligados_id": "group_mkykx7wz",
        "dept_keywords": ["SPT"],
    },
    "ATP": {
        "board_id": "18411735127",
        "board_name": "[Py] ATP - RH",
        "grupo_base_id": "topics",
        "grupo_desligados_id": "group_mkykx7wz",
        "dept_keywords": ["ATP"],
    },
    "FLUIDOS_MAR": {
        "board_id": "18411735241",
        "board_name": "[Py] Fluidos e Mar - RH",
        "grupo_base_id": "topics",
        "grupo_desligados_id": "group_mkykx7wz",
        "dept_keywords": ["FLUIDOS", "SERGIPE MAR"],
    },
}

DESTINATION_EXECUTION_ORDER: List[str] = list(DESTINATIONS.keys())

# ---------------------------------------------------------------------------
# colunas para score de completude (detecção de duplicados)
# ---------------------------------------------------------------------------

COMPLETENESS_COLS: List[str] = [
    COL_DEST_ORIGIN_ITEM_ID,
    COL_DEPARTAMENTO,
    COL_SALARIO_BASE,
    COL_SALARIO_BRUTO,
    COL_VALOR_LIQUIDO,
]

# ---------------------------------------------------------------------------
# ordem visual das colunas do board destino RH (~41 colunas)
# ---------------------------------------------------------------------------

RH_DEST_COLUMN_IDS_ORDER: List[str] = [
    "text_mkygmb51",
    "dropdown_mkygtfxa",
    "date_mkygqgpg",
    "date_mkygpzdj",
    "numeric_mkygexd3",
    "numeric_mkygwetb",
    "dropdown_mkygzk0c",
    "color_mkykbpd9",
    "text_mkygfwcb",
    "numeric_mkyg7gcz",
    "numeric_mkyg4ntk",
    "numeric_mkygy36x",
    "numeric_mkygc35k",
    "numeric_mkyg4sxh",
    "numeric_mkygem8t",
    "numeric_mkyghan2",
    "numeric_mkygyd3f",
    "numeric_mkygszsc",
    "numeric_mkyg4b6z",
    "numeric_mkygr28t",
    "numeric_mkygq1kw",
    "numeric_mkyg4ps0",
    "numeric_mkygkj83",
    "numeric_mkygyghy",
    "numeric_mkygfncd",
    "numeric_mkygwvm8",
    "numeric_mkygr1q0",
    "numeric_mkygrarn",
    "numeric_mkygpfpj",
    "numeric_mkygfn51",
    "numeric_mkygqnp1",
    "numeric_mkygq88y",
    "dropdown_mkyg8bk0",
    "numeric_mkyghbhy",
    "numeric_mkygtt6r",
    "dropdown_mkyggf0y",
    "numeric_mkyg16f9",
    "numeric_mkyg24cy",
    "numeric_mkygqah7",
    "numeric_mkygg20m",
    "date_mkyg7thh",
]

# mapeamento destino→origem quando os IDs de coluna diferem entre boards
DEST_TO_SOURCE_COLUMN_ID_MAP: Dict[str, str] = {
    "color_mkykbpd9": "dropdown_mm11en3g",  # Motivo desligamento: dropdown(origem) → status(destino)
}

RH_COLUMN_ID_TO_TITLE: Dict[str, str] = {
    "text_mkygmb51": "CPF Funcionario",
    "dropdown_mkygtfxa": "Departamento",
    "date_mkygqgpg": "Admissao",
    "date_mkygpzdj": "Demissao",
    "numeric_mkygexd3": "Valor TRCT",
    "numeric_mkygwetb": "Valor GRRF",
    "dropdown_mkygzk0c": "Tipo desligamento",
    "color_mkykbpd9": "Motivo desligamento",
    "text_mkygfwcb": "Funcao",
    "numeric_mkyg7gcz": "Salario Base",
    "numeric_mkyg4ntk": "Salario Mes",
    "numeric_mkygy36x": "Adicionais",
    "numeric_mkygc35k": "Salario Bruto",
    "numeric_mkyg4sxh": "Valor liquido",
    "numeric_mkygem8t": "Periculosidade 30%",
    "numeric_mkyghan2": "Periculosidade 30% Sobre HE",
    "numeric_mkygyd3f": "Sobreaviso",
    "numeric_mkygszsc": "AHRA 32,5%",
    "numeric_mkyg4b6z": "GRATIFICACAO LIDERANCA",
    "numeric_mkygr28t": "GRATIFICACAO",
    "numeric_mkygq1kw": "INTERINIDADE",
    "numeric_mkyg4ps0": "Confinamento",
    "numeric_mkygkj83": "Ad Noturno",
    "numeric_mkygyghy": "ADIANTAMENTO 13 SALARIO",
    "numeric_mkygfncd": "ABONO INDENIZATORIO ACT 2024/2025",
    "numeric_mkygwvm8": "hora extra 100%",
    "numeric_mkygr1q0": "hora extra 50%",
    "numeric_mkygrarn": "Hora extra curso",
    "numeric_mkygpfpj": "DSR",
    "numeric_mkygfn51": "FERIAS LIQUIDO",
    "numeric_mkygqnp1": "VA",
    "numeric_mkygq88y": "VR",
    "dropdown_mkyg8bk0": "Plano de saude",
    "numeric_mkyghbhy": "QTD dependente Plano de saude",
    "numeric_mkygtt6r": "Valor plano de saude",
    "dropdown_mkyggf0y": "Plano odontologico",
    "numeric_mkyg16f9": "QTD dependente Plano odontologico",
    "numeric_mkyg24cy": "Valor plano odontologico",
    "numeric_mkygqah7": "Seguro de vida",
    "numeric_mkygg20m": "Transporte",
    "date_mkyg7thh": "Competencia",
}

# ---------------------------------------------------------------------------
# mapas de normalização (preservar TODAS as variações de encoding quebrado)
# ---------------------------------------------------------------------------

MAP_TIPO_DESLIGAMENTO: Dict[str, str] = {
    "DEMITIDO": "DEMITIDO",
    "PEDIDO": "PEDIDO",
    "TERMINO DE CONTRATO": "TÉRMINO DE CONTRATO",
    "T?RMINO DE CONTRATO": "TÉRMINO DE CONTRATO",
    "T?RMINO DE CONTRATO": "TÉRMINO DE CONTRATO",
    "T??RMINO DE CONTRATO": "TÉRMINO DE CONTRATO",
    "T?RMINO DE CONTRATO": "TÉRMINO DE CONTRATO",
    "TéRMINO DE CONTRATO": "TÉRMINO DE CONTRATO",
    "T�RMINO DE CONTRATO": "TÉRMINO DE CONTRATO",
}

MAP_MOTIVO_DESLIGAMENTO: Dict[str, str] = {
    "Ajuste de quadro": "Ajuste de quadro",
    "Aposentado": "Aposentado",
    "COMPORTAMENTO INADEQUADO": "COMPORTAMENTO INADEQUADO",
    "Decisao gerencial": "Decisao gerencial",
    "Decisão gerencial": "Decisao gerencial",
    "Dispensa por estrategia de gestao": "Dispensa por estrategia de gestao",
    "Dispensa por estratégia de gestão": "Dispensa por estrategia de gestao",
    "Dispensado por iniciativa da empresa": "Dispensado por iniciativa da empresa",
    "INCOMPATIBILIDADE CULTURAL": "INCOMPATIBILIDADE CULTURAL",
    "Iniciativa da empresa": "Dispensado por iniciativa da empresa",
    "Nao divulgou o motivo.": "Nao divulgou o motivo",
    "Não divulgou o motivo.": "Nao divulgou o motivo",
    "Questoes Pessoais": "Questoes Pessoais",
    "Questões Pessoais": "Questoes Pessoais",
    "RETORNO DO AFASTAMENTO": "RETORNO DO AFASTAMENTO",
    "Reducao de Quadro": "Reducao de Quadro",
    "Redução de Quadro": "Reducao de Quadro",
    "Reducao de quadro": "Reducao de quadro",
    "Redução de quadro": "Reducao de quadro",
    "Retorno do INSS": "Retorno do INSS",
    "Saiu por questoes pessoais": "Questoes Pessoais",
    "Saiu por questões pessoais": "Questoes Pessoais",
    "Sem justificativa": "Sem justificativa",
    "Sem Justificativa": "Sem justificativa",
    "sem justificativa": "Sem justificativa",
    "Termino contrato": "Termino contrato",
    "Término contrato": "Termino contrato",
    "Termino contrato SPT": "Termino contrato SPT",
    "Termino contrato de experiencia": "Termino contrato de experiencia",
    "Termino contrato de experiência": "Termino contrato de experiencia",
    "termino contrato": "Termino contrato",
    "OUTRA PROPOSTA": "OUTRA PROPOSTA",
    "Outra Proposta": "OUTRA PROPOSTA",
    "Outra proposta": "OUTRA PROPOSTA",
    # variações com encoding quebrado (??)
    "CONTRATAçãO DE OUTRO MEDICO PJ": "CONTRATACAO DE OUTRO MEDICO PJ",
    "EFETIVAçãO": "EFETIVACAO",
    "REDUçãO DO TIME": "REDUCAO DO TIME",
    "Redução de quadro devido a parada da SPT 61 - Origem": "REDUCAO DE QUADRO DEVIDO A PARADA DA SPT 61 - ORIGEM",
    "Solicitação da Gerência": "Solicitacao da Gerencia",
    "TéRMINO DE CONTRATO": "Termino contrato",
    # variações com encoding quebrado (replacement char �)
    "CONTRATA��O DE OUTRO MEDICO PJ": "CONTRATACAO DE OUTRO MEDICO PJ",
    "EFETIVA��O": "EFETIVACAO",
    "REDU��O DO TIME": "REDUCAO DO TIME",
    "Redu��o de quadro devido a parada da SPT 61 - Origem": "REDUCAO DE QUADRO DEVIDO A PARADA DA SPT 61 - ORIGEM",
    "Solicita��o da Ger�ncia": "Solicitacao da Gerencia",
    "T�RMINO DE CONTRATO": "Termino contrato",
    # variações canônicas adicionais
    "CONTRATACAO DE OUTRO MEDICO PJ": "CONTRATACAO DE OUTRO MEDICO PJ",
    "CONTRATAÇÃO DE OUTRO MEDICO PJ": "CONTRATACAO DE OUTRO MEDICO PJ",
    "EFETIVACAO": "EFETIVACAO",
    "EFETIVAÇÃO": "EFETIVACAO",
    "REDUCAO DO TIME": "REDUCAO DO TIME",
    "REDUÇÃO DO TIME": "REDUCAO DO TIME",
    "REDUCAO DE QUADRO DEVIDO A PARADA DA SPT 61 - ORIGEM": "REDUCAO DE QUADRO DEVIDO A PARADA DA SPT 61 - ORIGEM",
    "REDUÇÃO DE QUADRO DEVIDO A PARADA DA SPT 61 - ORIGEM": "REDUCAO DE QUADRO DEVIDO A PARADA DA SPT 61 - ORIGEM",
    "Solicitacao da Gerencia": "Solicitacao da Gerencia",
    "Solicitação da Gerência": "Solicitacao da Gerencia",
    "TERMINO DE CONTRATO": "Termino contrato",
    "TÉRMINO DE CONTRATO": "Termino contrato",
}

MOTIVO_DESLIGAMENTO_STATUS_DEFAULT: str = ""
MOTIVO_DESLIGAMENTO_STATUS_ALLOWED: str = ""

MAP_PLANO_SAUDE: Dict[str, str] = {
    "AMIL": "AMIL",
    "Amil": "AMIL",
    "Amil/Hapvida": "Amil/Hapvida",
    "Amil/Plamed": "Amil/Plamed",
    "BRADESCO SAUDE": "BRADESCO SAUDE",
    "Bradesco Saúde": "BRADESCO SAUDE",
    "HAPVIDA": "HAPVIDA",
    "Hapvida": "HAPVIDA",
    "Hapvida/Plamed": "Hapvida/Plamed",
    "PLAMED": "PLAMED",
    "Palmed": "Palmed",
    "Plamed": "PLAMED",
}

MAP_PLANO_ODONTOLOGICO: Dict[str, str] = {
    "ODONTOPREV": "ODONTOPREV",
    "Odontoprev": "ODONTOPREV",
    "SERVDONTO": "SERVDONTO",
    "Servdonto": "SERVDONTO",
}


# ---------------------------------------------------------------------------
# validação de ambiente
# ---------------------------------------------------------------------------

def check_required_envs() -> None:
    if not TOKEN_MONDAY:
        raise EnvironmentError("MONDAY_API_TOKEN não configurado. Defina no .env antes de executar.")

    print(f"{LOG_PREFIX} [INFO] === Configuração do pipeline ===")
    print(f"{LOG_PREFIX} [INFO] TOKEN_MONDAY      : {_mask_token(TOKEN_MONDAY)}")
    print(f"{LOG_PREFIX} [INFO] API_URL            : {API_URL}")
    print(f"{LOG_PREFIX} [INFO] MAX_RETRIES        : {MAX_RETRIES}")
    print(f"{LOG_PREFIX} [INFO] REQUEST_TIMEOUT    : {REQUEST_TIMEOUT}s")
    print(f"{LOG_PREFIX} [INFO] PAGE_LIMIT         : {PAGE_LIMIT}")
    print(f"{LOG_PREFIX} [INFO] SHOW_PROGRESS      : {SHOW_PROGRESS}")
    print(f"{LOG_PREFIX} [INFO] --- dry-runs ---")
    print(f"{LOG_PREFIX} [INFO] CREATE             : {CREATE_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] DELETE_DUPLICATE   : {DELETE_DUPLICATE_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] DELETE_WRONG_BOARD : {DELETE_WRONG_BOARD_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] DELETE_NO_ORIGIN   : {DELETE_NO_ORIGIN_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] UPDATE_CRITICAL    : {UPDATE_CRITICAL_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] MOVE_WRONG_GROUPS  : {MOVE_WRONG_GROUPS_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] ===================================")
