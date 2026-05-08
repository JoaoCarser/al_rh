from __future__ import annotations

import time

import pandas as pd
from tqdm import tqdm

from src.config.settings import ACTION_SLEEP_SECONDS, LOG_PREFIX
from src.core.monday.execute_monday_query import execute_monday_query


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def _run_delete(df_delete_input: pd.DataFrame, reason: str, dry_run: bool) -> pd.DataFrame:
    if df_delete_input.empty:
        return pd.DataFrame()

    mutation = """
    mutation ($item_id: ID!) {
      delete_item(item_id: $item_id) { id }
    }
    """

    rows = []
    for _, row in tqdm(df_delete_input.iterrows(), total=len(df_delete_input), desc=f"Delete {reason}"):
        item_id = str(row.get("dest_item_id", "")).strip()
        rec = {
            "reason": reason,
            "dest_item_id": item_id,
            "dest_board_id": row.get("dest_board_id"),
            "status": "",
            "error": None,
        }

        if dry_run:
            rec["status"] = "dry_run"
            rows.append(rec)
            continue

        try:
            execute_monday_query(
                query=mutation,
                variables={"item_id": item_id},
                operation_name=f"delete_{reason}",
            )
            rec["status"] = "deleted"
        except Exception as exc:
            rec["status"] = "error"
            rec["error"] = str(exc)[:1500]

        rows.append(rec)
        time.sleep(ACTION_SLEEP_SECONDS)

    df_result = pd.DataFrame(rows)
    deleted = int((df_result["status"] == "deleted").sum()) if not df_result.empty else 0
    dry = int((df_result["status"] == "dry_run").sum()) if not df_result.empty else 0
    log_info(f"Delete {reason}: deleted={deleted} | dry_run={dry}")
    return df_result


def run_delete_duplicate_items(df_dup_delete: pd.DataFrame, dry_run: bool = True) -> pd.DataFrame:
    return _run_delete(df_dup_delete, reason="duplicates", dry_run=dry_run)
