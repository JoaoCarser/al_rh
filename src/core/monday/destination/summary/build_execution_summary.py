from __future__ import annotations

import time
from typing import Any, List, Optional, Tuple

import pandas as pd

from src.config.settings import LOG_PREFIX


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def format_duration_min_ss(elapsed_seconds: float) -> str:
    total_seconds = max(0, int(round(elapsed_seconds)))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}.{seconds:02d}"


def _count_status(df: Optional[pd.DataFrame], ok_statuses: List[str]) -> Tuple[int, int, int]:
    if df is None or df.empty:
        return 0, 0, 0
    planned = int(len(df))
    success = int(df["status"].isin(ok_statuses).sum()) if "status" in df.columns else 0
    error = int((df["status"] == "error").sum()) if "status" in df.columns else 0
    return planned, success, error


def build_df_execution_summary(
    pipeline_start_ts: float,
    df_create_result: pd.DataFrame,
    df_recreate_create_result: pd.DataFrame,
    df_divergent_items: pd.DataFrame,
    df_delete_duplicates_result: pd.DataFrame,
    df_delete_wrong_boards_result: pd.DataFrame,
    df_delete_no_origin_result: pd.DataFrame,
    df_move_wrong_groups_result: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    p, s, e = _count_status(df_create_result, ["created", "dry_run"])
    rows.append({"ACTION": "CREATE DESTINATION ITEMS", "PLANNED": p, "SUCCESS": s, "ERROR": e})

    planned_recreate = int(len(df_divergent_items)) if df_divergent_items is not None else 0
    _, s_rec, e_rec = _count_status(df_recreate_create_result, ["created", "dry_run"])
    rows.append({"ACTION": "RECREATE CRITICAL FIELDS", "PLANNED": planned_recreate, "SUCCESS": s_rec, "ERROR": e_rec})

    p, s, e = _count_status(df_delete_duplicates_result, ["deleted", "dry_run"])
    rows.append({"ACTION": "DELETE DUPLICATES", "PLANNED": p, "SUCCESS": s, "ERROR": e})

    p, s, e = _count_status(df_delete_wrong_boards_result, ["deleted", "dry_run"])
    rows.append({"ACTION": "DELETE WRONG BOARDS", "PLANNED": p, "SUCCESS": s, "ERROR": e})

    p, s, e = _count_status(df_delete_no_origin_result, ["deleted", "dry_run"])
    rows.append({"ACTION": "DELETE NO ORIGIN", "PLANNED": p, "SUCCESS": s, "ERROR": e})

    p, s, e = _count_status(df_move_wrong_groups_result, ["moved", "dry_run"])
    rows.append({"ACTION": "MOVE WRONG GROUPS", "PLANNED": p, "SUCCESS": s, "ERROR": e})

    duration_fmt = format_duration_min_ss(time.time() - pipeline_start_ts)
    rows.append({"ACTION": "PIPELINE DURATION (MIN)", "PLANNED": duration_fmt, "SUCCESS": "", "ERROR": ""})

    df_summary = pd.DataFrame(rows)
    log_info("Summary construido.")
    return df_summary


def build_df_actual_by_dest(df_destino_final: pd.DataFrame) -> pd.DataFrame:
    if df_destino_final.empty:
        return pd.DataFrame(columns=["dest_key", "ACTUAL_ROWS"])
    df_actual_by_dest = (
        df_destino_final[df_destino_final["id_origem_norm"].astype(str).str.strip() != ""]
        .groupby("dest_key", as_index=False)
        .size()
        .rename(columns={"size": "ACTUAL_ROWS"})
    )
    return df_actual_by_dest


def build_df_reconcile_by_dest(
    df_expected_by_dest: pd.DataFrame,
    df_actual_by_dest: pd.DataFrame,
) -> pd.DataFrame:
    df_reconcile = df_expected_by_dest.merge(df_actual_by_dest, on="dest_key", how="outer").fillna(0)
    df_reconcile["EXPECTED_ROWS"] = df_reconcile["EXPECTED_ROWS"].astype(int)
    df_reconcile["ACTUAL_ROWS"] = df_reconcile["ACTUAL_ROWS"].astype(int)
    df_reconcile["DELTA"] = df_reconcile["ACTUAL_ROWS"] - df_reconcile["EXPECTED_ROWS"]
    df_reconcile = df_reconcile.rename(columns={"dest_key": "DEST_KEY"})
    df_reconcile = df_reconcile.sort_values("DEST_KEY").reset_index(drop=True)
    return df_reconcile
