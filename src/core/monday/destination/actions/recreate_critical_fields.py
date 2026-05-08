from __future__ import annotations

from typing import Tuple

import pandas as pd

from src.config.settings import DESTINATION_EXECUTION_ORDER, LOG_PREFIX
from src.core.monday.destination.actions.create_monday_items import build_df_create_results
from src.core.monday.destination.actions.duplicates.delete_duplicate_items import _run_delete
from src.core.monday.destination.payload.build_create_payload import build_df_payload
from src.core.monday.origin.enrich_origin_items import build_df_enriched


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def run_recreate_critical_fields(
    df_divergent_items: pd.DataFrame,
    df_or_val: pd.DataFrame,
    dry_run: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df_divergent_items.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_to_delete = df_divergent_items[["dest_item_id", "dest_board_id"]].drop_duplicates().copy()
    log_info(f"Critical recreate: delete stage | planned={len(df_to_delete)} | dry_run={dry_run}")

    df_delete_result = _run_delete(df_to_delete, reason="critical_recreate", dry_run=dry_run)

    if dry_run:
        recreate_ids = set(df_divergent_items["origem_item_id"].astype(str))
    else:
        ok_deleted = df_delete_result[df_delete_result["status"] == "deleted"]
        deleted_dest_ids = set(ok_deleted["dest_item_id"].astype(str))
        recreate_ids = set(
            df_divergent_items[
                df_divergent_items["dest_item_id"].astype(str).isin(deleted_dest_ids)
            ]["origem_item_id"].astype(str)
        )

    df_recreate_seed = df_or_val[
        df_or_val["origem_item_id"].astype(str).isin(recreate_ids)
    ].copy()
    log_info(f"Critical recreate: enrich stage | seed={len(df_recreate_seed)}")

    df_raw, _, df_enrich_missing = build_df_enriched(df_recreate_seed)
    log_info(f"Critical recreate: payload stage | raw={len(df_raw)} | missing={len(df_enrich_missing)}")

    df_payload = build_df_payload(df_raw)
    payload_ok = int((df_payload["payload_status"] == "ok").sum()) if not df_payload.empty else 0
    log_info(f"Critical recreate: create stage | payload_ok={payload_ok}")

    df_create_result, _ = build_df_create_results(
        df_payload,
        dry_run=dry_run,
        execution_order=DESTINATION_EXECUTION_ORDER,
    )

    return df_to_delete, df_delete_result, df_recreate_seed, df_create_result, df_enrich_missing
