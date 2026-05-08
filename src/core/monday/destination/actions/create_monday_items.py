from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    CREATE_SLEEP_SECONDS,
    DESTINATION_EXECUTION_ORDER,
    LOG_PREFIX,
)
from src.core.monday.execute_monday_query import execute_monday_query


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def build_df_create_results(
    df_payload_ready: pd.DataFrame,
    dry_run: bool = True,
    execution_order: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df_payload_ready.empty:
        return pd.DataFrame(), pd.DataFrame()

    mutation = """
    mutation ($board_id: ID!, $group_id: String!, $item_name: String!, $column_values: JSON!) {
      create_item(board_id: $board_id, group_id: $group_id, item_name: $item_name, column_values: $column_values) { id }
    }
    """

    order = execution_order or DESTINATION_EXECUTION_ORDER
    df_payload_ok = df_payload_ready[df_payload_ready["payload_status"] == "ok"].copy()

    rows: List[Dict[str, Any]] = []

    for dest_key in order:
        df_board = df_payload_ok[df_payload_ok["dest_key"] == dest_key].copy()
        if df_board.empty:
            log_info(f"Create board {dest_key}: sem itens para criar")
            continue

        planned = len(df_board)
        log_info(f"Create board {dest_key}: inicio | planned={planned} | dry_run={dry_run}")

        board_success = 0
        board_error = 0

        for _, row in tqdm(df_board.iterrows(), total=planned, desc=f"Create {dest_key}"):
            rec: Dict[str, Any] = {
                "origem_item_id": row["origem_item_id"],
                "name": row["name"],
                "dest_key": row["dest_key"],
                "dest_board_id": row["dest_board_id"],
                "dest_group_id": row["dest_group_id"],
                "status": "",
                "dest_item_id_created": None,
                "error": None,
            }

            if dry_run:
                rec["status"] = "dry_run"
                rows.append(rec)
                board_success += 1
                continue

            try:
                data = execute_monday_query(
                    query=mutation,
                    variables={
                        "board_id": row["dest_board_id"],
                        "group_id": row["dest_group_id"],
                        "item_name": row["name"],
                        "column_values": row["column_values_json"],
                    },
                    operation_name=f"create_items_{dest_key}",
                )
                created = data.get("create_item") or {}
                created_id = str(created.get("id", "")).strip()
                if created_id:
                    rec["status"] = "created"
                    rec["dest_item_id_created"] = created_id
                    board_success += 1
                else:
                    rec["status"] = "error"
                    rec["error"] = f"create_item sem id retornado. data={str(data)[:500]}"
                    board_error += 1
            except Exception as exc:
                rec["status"] = "error"
                rec["error"] = str(exc)[:1500]
                board_error += 1

            rows.append(rec)
            time.sleep(CREATE_SLEEP_SECONDS)

        log_info(f"Create board {dest_key}: fim | success={board_success} | error={board_error}")

    df_create_result = pd.DataFrame(rows)
    if df_create_result.empty:
        return df_create_result, pd.DataFrame()

    df_create_board_summary = (
        df_create_result.groupby(["dest_key", "status"], as_index=False)
        .size()
        .rename(columns={"size": "qtd"})
        .sort_values(["dest_key", "status"])
        .reset_index(drop=True)
    )
    return df_create_result, df_create_board_summary
