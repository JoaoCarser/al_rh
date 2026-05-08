from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    DEST_TO_SOURCE_COLUMN_ID_MAP,
    LOG_PREFIX,
    RH_COLUMN_ID_TO_TITLE,
    RH_DEST_COLUMN_IDS_ORDER,
)
from src.core.monday.execute_monday_query import (
    _extract_column_maps,
    query_items_by_ids,
)
from src.core.utils import as_decimal


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def log_warn(message: str) -> None:
    print(f"{LOG_PREFIX} [WARN] {message}")


def _safe_json_load(raw_value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _to_internal_value(
    dest_col_id: str,
    text_value: Optional[str],
    raw_value: Optional[str],
) -> Optional[Any]:
    txt = (text_value or "").strip()

    if dest_col_id.startswith("dropdown_"):
        labels = [x.strip() for x in txt.split(",") if x.strip()]
        return {"labels": labels} if labels else None

    if dest_col_id.startswith("color_"):
        return {"label": txt} if txt else None

    if dest_col_id.startswith("date_"):
        parsed = _safe_json_load(raw_value)
        if parsed and parsed.get("date"):
            return {"date": str(parsed["date"])[:10]}
        if re.match(r"^\d{4}-\d{2}-\d{2}$", txt):
            return {"date": txt}
        return None

    if dest_col_id.startswith("numeric_"):
        return as_decimal(txt)

    if dest_col_id.startswith("text_"):
        return txt if txt else ""

    return txt if txt else None


def _to_view_value(value: Any) -> Any:
    if isinstance(value, dict):
        if "labels" in value:
            return ", ".join(str(x) for x in value.get("labels", []))
        if "label" in value:
            return str(value.get("label") or "")
        if "date" in value:
            return str(value.get("date") or "")
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else value


def build_df_enriched(
    df_novos: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df_novos.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    ids_needed = sorted({
        str(x).strip()
        for x in df_novos["origem_item_id"].dropna().astype(str)
        if str(x).strip()
    })

    source_column_ids = sorted({
        DEST_TO_SOURCE_COLUMN_ID_MAP.get(c, c) for c in RH_DEST_COLUMN_IDS_ORDER
    })

    log_info(f"Enrich: consultando {len(ids_needed)} IDs de origem...")

    origin_items = query_items_by_ids(
        item_ids=ids_needed,
        column_ids=source_column_ids,
        operation_name="enrich_new_items_by_ids_rh",
        chunk_size=25,
    )
    by_id = {str(item.get("id", "")).strip(): item for item in origin_items}

    missing_ids = [iid for iid in ids_needed if iid not in by_id]
    if missing_ids:
        log_warn(f"Enrich: primeira passada faltando {len(missing_ids)} IDs. Tentando fallback...")
        fallback_items = query_items_by_ids(
            item_ids=missing_ids,
            column_ids=source_column_ids,
            operation_name="enrich_new_items_by_ids_rh_fallback",
            chunk_size=10,
        )
        for it in fallback_items:
            iid = str(it.get("id", "")).strip()
            if iid and iid not in by_id:
                by_id[iid] = it

    rows_raw: List[Dict[str, Any]] = []
    rows_view: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, Any]] = []

    for _, row in tqdm(df_novos.iterrows(), total=len(df_novos), desc="Enriquecendo novos itens RH"):
        origem_item_id = str(row["origem_item_id"]).strip()
        item = by_id.get(origem_item_id)

        if not item:
            missing_rows.append({
                "origem_item_id": origem_item_id,
                "name": row.get("name", ""),
                "dest_key": row.get("dest_key", ""),
                "dest_board_id": row.get("dest_board_id", ""),
            })
            continue

        cmap = _extract_column_maps(item.get("column_values", []))

        raw_rec: Dict[str, Any] = {
            "origem_item_id": origem_item_id,
            "name": row.get("name", ""),
            "cpf": row.get("cpf", ""),
            "departamento": row.get("departamento", ""),
            "motivo_desligamento": row.get("motivo_desligamento", ""),
            "dest_key": row.get("dest_key", ""),
            "dest_group_id": row.get("dest_group_id", ""),
            "dest_board_id": row.get("dest_board_id", ""),
        }

        view_rec: Dict[str, Any] = {
            "origem_item_id": origem_item_id,
            "name": row.get("name", ""),
            "cpf": row.get("cpf", ""),
            "departamento": row.get("departamento", ""),
            "motivo_desligamento": row.get("motivo_desligamento", ""),
            "dest_key": row.get("dest_key", ""),
            "dest_group_id": row.get("dest_group_id", ""),
            "dest_board_id": row.get("dest_board_id", ""),
        }

        for dest_col_id in RH_DEST_COLUMN_IDS_ORDER:
            source_col_id = DEST_TO_SOURCE_COLUMN_ID_MAP.get(dest_col_id, dest_col_id)
            parsed_col = _to_internal_value(
                dest_col_id=dest_col_id,
                text_value=cmap.get(source_col_id, {}).get("text"),
                raw_value=cmap.get(source_col_id, {}).get("value"),
            )
            raw_rec[dest_col_id] = parsed_col
            view_rec[RH_COLUMN_ID_TO_TITLE.get(dest_col_id, dest_col_id)] = _to_view_value(parsed_col)

        rows_raw.append(raw_rec)
        rows_view.append(view_rec)

    df_to_create_raw = pd.DataFrame(rows_raw)
    df_to_create_view = pd.DataFrame(rows_view)
    df_enrich_missing = pd.DataFrame(missing_rows)

    control_view_cols = ["origem_item_id", "name", "dest_key", "dest_group_id", "dest_board_id"]
    ordered_business_cols = [RH_COLUMN_ID_TO_TITLE[c] for c in RH_DEST_COLUMN_IDS_ORDER]
    view_order = control_view_cols + ordered_business_cols

    for col in view_order:
        if col not in df_to_create_view.columns:
            df_to_create_view[col] = ""
    if not df_to_create_view.empty:
        df_to_create_view = df_to_create_view[view_order]

    log_info(
        f"Enrich concluido. raw={len(df_to_create_raw)} "
        f"| view={len(df_to_create_view)} "
        f"| missing={len(df_enrich_missing)}"
    )
    return df_to_create_raw, df_to_create_view, df_enrich_missing
