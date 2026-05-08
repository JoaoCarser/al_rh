from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    COL_DEPARTAMENTO,
    COL_DEST_ORIGIN_ITEM_ID,
    COL_MOTIVO_DESLIGAMENTO_DESTINO,
    COL_SALARIO_BASE,
    COL_SALARIO_BRUTO,
    COL_TIPO_DESLIGAMENTO,
    COL_VALOR_LIQUIDO,
    DESTINATION_EXECUTION_ORDER,
    DESTINATIONS,
    LOG_PREFIX,
)
from src.core.monday.execute_monday_query import (
    _extract_column_maps,
    query_board_items_minimal,
)
from src.core.utils import _canonical_origin_id


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def build_df_cur_des() -> pd.DataFrame:
    cols = [
        COL_DEST_ORIGIN_ITEM_ID,
        COL_DEPARTAMENTO,
        COL_MOTIVO_DESLIGAMENTO_DESTINO,
        COL_TIPO_DESLIGAMENTO,
        COL_SALARIO_BASE,
        COL_SALARIO_BRUTO,
        COL_VALOR_LIQUIDO,
    ]

    rows: List[Dict[str, Any]] = []

    for dest_key in DESTINATION_EXECUTION_ORDER:
        cfg = DESTINATIONS[dest_key]
        board_id = str(cfg["board_id"])
        board_name = str(cfg.get("board_name") or board_id)

        items = query_board_items_minimal(
            board_id=board_id,
            column_ids=cols,
            board_name=board_name,
            max_cursor_restarts=6,
            empty_page_retries=2,
        )

        for it in tqdm(items, desc=f"Processando destino {dest_key}"):
            cmap = _extract_column_maps(it.get("column_values", []))
            group = it.get("group") or {}

            id_origem = (cmap.get(COL_DEST_ORIGIN_ITEM_ID, {}).get("text") or "").strip()
            id_origem_norm = _canonical_origin_id(id_origem)
            departamento = (cmap.get(COL_DEPARTAMENTO, {}).get("text") or "").strip()
            motivo_desligamento = (cmap.get(COL_MOTIVO_DESLIGAMENTO_DESTINO, {}).get("text") or "").strip()
            tipo_desligamento = (cmap.get(COL_TIPO_DESLIGAMENTO, {}).get("text") or "").strip()

            rows.append({
                "dest_item_id": str(it.get("id", "")).strip(),
                "name": (it.get("name") or "").strip(),
                "id_origem": id_origem,
                "id_origem_norm": id_origem_norm,
                "departamento": departamento,
                "motivo_desligamento": motivo_desligamento,
                "tipo_desligamento": tipo_desligamento,
                "dest_group_title": str(group.get("title") or "").strip(),
                "dest_key": dest_key,
                "dest_board_name": board_name,
                "dest_board_id": board_id,
                "dest_salario_base": cmap.get(COL_SALARIO_BASE, {}).get("text"),
                "dest_salario_bruto": cmap.get(COL_SALARIO_BRUTO, {}).get("text"),
                "dest_valor_liquido": cmap.get(COL_VALOR_LIQUIDO, {}).get("text"),
            })

    ordered_cols = [
        "dest_item_id",
        "name",
        "id_origem",
        "id_origem_norm",
        "departamento",
        "motivo_desligamento",
        "tipo_desligamento",
        "dest_group_title",
        "dest_key",
        "dest_board_name",
        "dest_board_id",
        "dest_salario_base",
        "dest_salario_bruto",
        "dest_valor_liquido",
    ]

    if rows:
        df_cur_des = pd.DataFrame(rows)[ordered_cols]
    else:
        df_cur_des = pd.DataFrame(columns=ordered_cols)

    log_info(f"Fetch destinos concluido. total_itens={len(df_cur_des)}")
    return df_cur_des
