from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    COL_DEPARTAMENTO,
    COL_MOTIVO_DESLIGAMENTO_ORIGEM,
    COL_SALARIO_BASE,
    COL_SALARIO_BRUTO,
    COL_TIPO_DESLIGAMENTO,
    COL_VALOR_LIQUIDO,
    LOG_PREFIX,
    ORIGIN_BOARDS,
)
from src.core.monday.execute_monday_query import (
    _extract_column_maps,
    query_board_items_minimal,
)
from src.core.utils import _canonical_origin_id


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def build_df_or() -> pd.DataFrame:
    cols = [
        "text_mkygmb51",               # CPF
        COL_DEPARTAMENTO,
        COL_MOTIVO_DESLIGAMENTO_ORIGEM,
        COL_TIPO_DESLIGAMENTO,
        COL_SALARIO_BASE,
        COL_SALARIO_BRUTO,
        COL_VALOR_LIQUIDO,
    ]

    rows: List[Dict[str, Any]] = []

    for origin_cfg in ORIGIN_BOARDS:
        board_id = str(origin_cfg["board_id"])
        board_name = str(origin_cfg.get("board_name") or board_id)

        items = query_board_items_minimal(
            board_id=board_id,
            column_ids=cols,
            board_name=board_name,
        )

        for it in tqdm(items, desc=f"Processando origem {board_name}"):
            cmap = _extract_column_maps(it.get("column_values", []))
            group = it.get("group") or {}

            cpf = (cmap.get("text_mkygmb51", {}).get("text") or "").strip()
            departamento = (cmap.get(COL_DEPARTAMENTO, {}).get("text") or "").strip()
            motivo_desligamento = (cmap.get(COL_MOTIVO_DESLIGAMENTO_ORIGEM, {}).get("text") or "").strip()
            tipo_desligamento = (cmap.get(COL_TIPO_DESLIGAMENTO, {}).get("text") or "").strip()

            rows.append({
                "origem_item_id": str(it.get("id", "")).strip(),
                "id_origem_norm": _canonical_origin_id(it.get("id", "")),
                "name": (it.get("name") or "").strip(),
                "cpf": cpf,
                "departamento": departamento,
                "motivo_desligamento": motivo_desligamento,
                "tipo_desligamento": tipo_desligamento,
                "origem_group_title": str(group.get("title") or "").strip(),
                "origin_board_name": board_name,
                "origin_board_id": board_id,
                "orig_salario_base": cmap.get(COL_SALARIO_BASE, {}).get("text"),
                "orig_salario_bruto": cmap.get(COL_SALARIO_BRUTO, {}).get("text"),
                "orig_valor_liquido": cmap.get(COL_VALOR_LIQUIDO, {}).get("text"),
            })

    ordered_cols = [
        "origem_item_id",
        "id_origem_norm",
        "name",
        "cpf",
        "departamento",
        "motivo_desligamento",
        "tipo_desligamento",
        "origem_group_title",
        "origin_board_name",
        "origin_board_id",
        "orig_salario_base",
        "orig_salario_bruto",
        "orig_valor_liquido",
    ]

    if rows:
        df_or = pd.DataFrame(rows)[ordered_cols]
    else:
        df_or = pd.DataFrame(columns=ordered_cols)

    log_info(f"Fetch origem concluido. total_itens={len(df_or)}")
    return df_or
