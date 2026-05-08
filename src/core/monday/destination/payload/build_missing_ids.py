from __future__ import annotations

from typing import Tuple

import pandas as pd

from src.config.settings import DESTINATIONS, LOG_PREFIX
from src.core.utils import (
    _canonical_origin_id,
    get_dest_key_by_departamento,
    get_target_group_id,
    normalize_text,
)


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def filter_dept_valid(df_or: pd.DataFrame) -> pd.DataFrame:
    if df_or.empty:
        cols = list(df_or.columns) + ["departamento_norm", "dest_key", "dest_board_id", "dest_group_id"]
        return pd.DataFrame(columns=list(dict.fromkeys(cols)))

    df = df_or.copy()
    df["departamento_norm"] = df["departamento"].map(normalize_text)
    df["dest_key"] = df["departamento"].map(get_dest_key_by_departamento)

    def _resolve_dest_board_id(dest_key) -> str:
        if not dest_key or dest_key not in DESTINATIONS:
            return ""
        return str(DESTINATIONS[dest_key]["board_id"])

    def _resolve_dest_group_id(row: pd.Series) -> str:
        dest_key = row.get("dest_key")
        if not dest_key or dest_key not in DESTINATIONS:
            return ""
        cfg = DESTINATIONS[dest_key]
        return get_target_group_id(cfg, row.get("motivo_desligamento"), row.get("tipo_desligamento"))

    df["dest_board_id"] = df["dest_key"].map(_resolve_dest_board_id)
    df["dest_group_id"] = df.apply(_resolve_dest_group_id, axis=1)

    df_or_val = df[df["dest_key"].notna()].copy()

    sem_destino = int((df["dest_key"].isna()).sum())
    log_info(f"Filter departamentos concluido. validos={len(df_or_val)} | sem_destino={sem_destino}")
    return df_or_val


def compare_origem_destino(
    df_or_val: pd.DataFrame,
    df_cur_des: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df_or_val.empty:
        return pd.DataFrame(columns=df_or_val.columns), pd.DataFrame()

    work_or = df_or_val.copy()
    if "id_origem_norm" not in work_or.columns:
        work_or["id_origem_norm"] = work_or["origem_item_id"].map(_canonical_origin_id)
    else:
        work_or["id_origem_norm"] = work_or["id_origem_norm"].map(_canonical_origin_id)

    work_or["expected_dest_board_id"] = work_or["dest_board_id"].astype(str).str.strip()

    work_de = df_cur_des.copy() if df_cur_des is not None else pd.DataFrame()
    if not work_de.empty:
        if "id_origem_norm" not in work_de.columns and "id_origem" in work_de.columns:
            work_de["id_origem_norm"] = work_de["id_origem"].map(_canonical_origin_id)
        elif "id_origem_norm" in work_de.columns:
            work_de["id_origem_norm"] = work_de["id_origem_norm"].map(_canonical_origin_id)
        else:
            work_de["id_origem_norm"] = ""

        if "dest_board_id" not in work_de.columns:
            work_de["dest_board_id"] = ""
        work_de["dest_board_id"] = work_de["dest_board_id"].astype(str).str.strip()
    else:
        work_de = pd.DataFrame(columns=["id_origem_norm", "dest_board_id"])

    existing_pairs = set(
        zip(
            work_de.loc[work_de["id_origem_norm"] != "", "id_origem_norm"],
            work_de.loc[work_de["id_origem_norm"] != "", "dest_board_id"],
        )
    )

    df_new_items = work_or[
        (work_or["id_origem_norm"] != "")
        & (~work_or.apply(
            lambda r: (r["id_origem_norm"], r["expected_dest_board_id"]) in existing_pairs,
            axis=1,
        ))
    ].copy()

    if work_de.empty:
        df_existing = pd.DataFrame()
    else:
        df_existing = work_or.merge(
            work_de,
            left_on=["id_origem_norm", "expected_dest_board_id"],
            right_on=["id_origem_norm", "dest_board_id"],
            how="inner",
            suffixes=("_origem", "_dest"),
        )

    log_info(
        f"Compare concluido. novos={len(df_new_items)} | existentes={len(df_existing)}"
    )
    return df_new_items, df_existing


def build_df_expected_by_dest(df_or_val: pd.DataFrame) -> pd.DataFrame:
    if df_or_val.empty:
        return pd.DataFrame(columns=["dest_key", "EXPECTED_ROWS"])
    df_expected_by_dest = (
        df_or_val.groupby("dest_key", as_index=False)
        .size()
        .rename(columns={"size": "EXPECTED_ROWS"})
        .sort_values("dest_key")
        .reset_index(drop=True)
    )
    return df_expected_by_dest
