from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    COL_DEST_ORIGIN_ITEM_ID,
    COL_MOTIVO_DESLIGAMENTO_DESTINO,
    LOG_PREFIX,
    MAP_MOTIVO_DESLIGAMENTO,
    MAP_PLANO_ODONTOLOGICO,
    MAP_PLANO_SAUDE,
    MAP_TIPO_DESLIGAMENTO,
    MOTIVO_DESLIGAMENTO_STATUS_DEFAULT,
    RH_DEST_COLUMN_IDS_ORDER,
)
from src.core.utils import as_decimal, normalize_text


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def _is_effectively_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (float, np.floating)):
        return not np.isfinite(value)
    if isinstance(value, dict):
        if "labels" in value:
            return len([x for x in value.get("labels", []) if str(x).strip()]) == 0
        if "label" in value:
            return str(value.get("label") or "").strip() == ""
        if "date" in value:
            return str(value.get("date") or "").strip() == ""
        return len(value) == 0
    return False


def _format_number_for_api(value: Any) -> Optional[float]:
    val = as_decimal(value)
    if val is None:
        return None
    if not np.isfinite(val):
        return None
    return float(val)


def _map_label_with_fallback(raw_label: str, mapping: Dict[str, str]) -> str:
    src = str(raw_label or "").strip()
    if not src:
        return ""
    if src in mapping:
        return str(mapping[src]).strip()

    src_norm = normalize_text(src)
    for k, v in mapping.items():
        if normalize_text(k) == src_norm:
            return str(v).strip()

    src_fix = src.replace("?", "?")
    if src_fix in mapping:
        return str(mapping[src_fix]).strip()

    return src


def build_df_payload(df_to_create_raw: pd.DataFrame) -> pd.DataFrame:
    if df_to_create_raw.empty:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []

    for _, row in tqdm(df_to_create_raw.iterrows(), total=len(df_to_create_raw), desc="Montando payload RH"):
        rec: Dict[str, Any] = {
            "origem_item_id": row.get("origem_item_id", ""),
            "name": row.get("name", ""),
            "dest_key": row.get("dest_key", ""),
            "dest_board_id": row.get("dest_board_id", ""),
            "dest_group_id": row.get("dest_group_id", ""),
            "payload_status": "",
            "payload_error": None,
            "column_values_json": None,
        }

        try:
            payload: Dict[str, Any] = {}

            payload[COL_DEST_ORIGIN_ITEM_ID] = str(row.get("origem_item_id", "")).strip()

            for col_id in RH_DEST_COLUMN_IDS_ORDER:
                val = row.get(col_id)
                if _is_effectively_empty(val):
                    continue

                if col_id.startswith("numeric_"):
                    num_val = _format_number_for_api(val)
                    if num_val is None:
                        continue
                    payload[col_id] = num_val

                elif col_id.startswith("text_"):
                    payload[col_id] = str(val).strip()

                elif col_id.startswith("date_"):
                    payload[col_id] = val

                elif col_id.startswith("dropdown_"):
                    if col_id == "dropdown_mkyg8bk0":  # Plano de saude
                        labels: List[str] = []
                        if isinstance(val, dict):
                            labels = [str(x).strip() for x in val.get("labels", []) if str(x).strip()]
                        elif isinstance(val, str) and val.strip():
                            labels = [val.strip()]
                        if labels:
                            mapped = MAP_PLANO_SAUDE.get(labels[0], labels[0])
                            if str(mapped).strip():
                                payload[col_id] = {"labels": [str(mapped).strip()]}

                    elif col_id == "dropdown_mkygzk0c":  # Tipo desligamento
                        labels = []
                        if isinstance(val, dict):
                            labels = [str(x).strip() for x in val.get("labels", []) if str(x).strip()]
                        elif isinstance(val, str) and val.strip():
                            labels = [val.strip()]
                        if labels:
                            mapped = _map_label_with_fallback(labels[0], MAP_TIPO_DESLIGAMENTO)
                            if str(mapped).strip():
                                payload[col_id] = {"labels": [str(mapped).strip()]}

                    elif col_id == "dropdown_mkyggf0y":  # Plano odontologico
                        labels = []
                        if isinstance(val, dict):
                            labels = [str(x).strip() for x in val.get("labels", []) if str(x).strip()]
                        elif isinstance(val, str) and val.strip():
                            labels = [val.strip()]
                        if labels:
                            mapped = MAP_PLANO_ODONTOLOGICO.get(labels[0], labels[0])
                            if str(mapped).strip():
                                payload[col_id] = {"labels": [str(mapped).strip()]}

                    else:
                        payload[col_id] = val

                elif col_id.startswith("color_"):
                    if col_id == COL_MOTIVO_DESLIGAMENTO_DESTINO:
                        label = ""
                        if isinstance(val, dict):
                            label = str(val.get("label") or "").strip()
                        else:
                            label = str(val or "").strip()

                        if label:
                            label_dest = MAP_MOTIVO_DESLIGAMENTO.get(label, MOTIVO_DESLIGAMENTO_STATUS_DEFAULT)
                            if str(label_dest).strip():
                                payload[col_id] = {"label": str(label_dest).strip()}
                    else:
                        payload[col_id] = val

                else:
                    payload[col_id] = val

            rec["column_values_json"] = json.dumps(payload, ensure_ascii=False)
            rec["payload_status"] = "ok"

        except Exception as exc:
            rec["payload_status"] = "erro"
            rec["payload_error"] = str(exc)[:1500]

        rows.append(rec)

    df_payload_ready = pd.DataFrame(rows)
    ok_count = int((df_payload_ready["payload_status"] == "ok").sum()) if not df_payload_ready.empty else 0
    err_count = int((df_payload_ready["payload_status"] == "erro").sum()) if not df_payload_ready.empty else 0
    log_info(f"Build payload concluido. ok={ok_count} | erro={err_count}")
    return df_payload_ready
