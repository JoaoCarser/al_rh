from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from src.config.settings import COMPLETENESS_COLS, LOG_PREFIX
from src.core.monday.execute_monday_query import (
    _extract_column_maps,
    query_items_by_ids,
)
from src.core.utils import _canonical_origin_id, as_decimal


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def _compute_completeness_score(cmap: Dict[str, Dict[str, Any]]) -> int:
    score = 0
    for col_id in COMPLETENESS_COLS:
        txt = (cmap.get(col_id, {}).get("text") or "").strip()
        if not txt:
            continue
        if col_id.startswith("numeric_"):
            num = as_decimal(txt)
            if num is not None and abs(num) > 0:
                score += 1
            continue
        score += 1
    return score


def build_df_duplicates(df_cur_des: pd.DataFrame) -> pd.DataFrame:
    if df_cur_des.empty:
        return pd.DataFrame()

    work = df_cur_des.copy()
    if "id_origem_norm" not in work.columns:
        if "id_origem" not in work.columns:
            return pd.DataFrame()
        work["id_origem_norm"] = work["id_origem"].map(_canonical_origin_id)
    else:
        work["id_origem_norm"] = work["id_origem_norm"].map(_canonical_origin_id)

    dup_base = work[work["id_origem_norm"].astype(str).str.strip() != ""].copy()
    dup_base = dup_base[dup_base.duplicated(subset=["dest_board_id", "id_origem_norm"], keep=False)]

    if dup_base.empty:
        log_info("Duplicados: nenhum encontrado.")
        return pd.DataFrame()

    item_ids = dup_base["dest_item_id"].astype(str).tolist()
    details = query_items_by_ids(
        item_ids=item_ids,
        column_ids=COMPLETENESS_COLS,
        operation_name="detect_duplicates",
    )
    score_by_item: Dict[str, int] = {}
    for item in details:
        iid = str(item.get("id", "")).strip()
        cmap = _extract_column_maps(item.get("column_values", []))
        score_by_item[iid] = _compute_completeness_score(cmap)

    work_dup = dup_base.copy()
    work_dup["completeness_score"] = work_dup["dest_item_id"].map(lambda x: score_by_item.get(str(x), 0))
    work_dup["dest_item_id_num"] = pd.to_numeric(work_dup["dest_item_id"], errors="coerce")
    work_dup = work_dup.sort_values(
        by=["dest_board_id", "id_origem_norm", "completeness_score", "dest_item_id_num"],
        ascending=[True, True, False, True],
        kind="stable",
    )
    work_dup["dup_rank"] = work_dup.groupby(["dest_board_id", "id_origem_norm"]).cumcount() + 1
    work_dup["action"] = np.where(work_dup["dup_rank"] == 1, "keep", "delete")

    df_dup_delete = work_dup[work_dup["action"] == "delete"].copy()
    log_info(f"Duplicados: encontrados={len(df_dup_delete)} para deletar.")
    return df_dup_delete
