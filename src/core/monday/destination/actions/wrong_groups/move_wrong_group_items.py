from __future__ import annotations

import time
from typing import Any, Dict, List

import pandas as pd
from tqdm import tqdm

from src.config.settings import ACTION_SLEEP_SECONDS, LOG_PREFIX
from src.core.monday.execute_monday_query import execute_monday_query


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def run_move_wrong_group_items(
    df_wrong_groups: pd.DataFrame,
    dry_run: bool = True,
) -> pd.DataFrame:
    if df_wrong_groups.empty:
        return pd.DataFrame()

    mutation = """
    mutation ($item_id: ID!, $group_id: String!) {
      move_item_to_group(item_id: $item_id, group_id: $group_id) { id }
    }
    """

    rows: List[Dict[str, Any]] = []

    for _, row in tqdm(df_wrong_groups.iterrows(), total=len(df_wrong_groups), desc="Move wrong group"):
        item_id = str(row.get("dest_item_id", "")).strip()
        expected_group_id = str(row.get("expected_group_id", "")).strip()

        rec: Dict[str, Any] = {
            "dest_item_id": item_id,
            "dest_board_id": str(row.get("dest_board_id", "")).strip(),
            "dest_key": row.get("dest_key", ""),
            "group_from": str(row.get("dest_group_id", "")).strip(),
            "group_to": expected_group_id,
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
                variables={"item_id": item_id, "group_id": expected_group_id},
                operation_name="move_wrong_group",
            )
            rec["status"] = "moved"
        except Exception as exc:
            rec["status"] = "error"
            rec["error"] = str(exc)[:1500]

        rows.append(rec)
        time.sleep(ACTION_SLEEP_SECONDS)

    df_move_result = pd.DataFrame(rows)
    moved = int((df_move_result["status"] == "moved").sum()) if not df_move_result.empty else 0
    dry = int((df_move_result["status"] == "dry_run").sum()) if not df_move_result.empty else 0
    log_info(f"Move wrong group: moved={moved} | dry_run={dry}")
    return df_move_result
