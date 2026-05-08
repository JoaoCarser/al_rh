from __future__ import annotations

import pandas as pd

from src.config.settings import LOG_PREFIX
from src.core.utils import _canonical_origin_id


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def build_df_wrong_boards(
    df_cur_des: pd.DataFrame,
    df_or_val: pd.DataFrame,
) -> pd.DataFrame:
    if df_cur_des.empty or df_or_val.empty:
        return pd.DataFrame()

    expected = (
        df_or_val[["id_origem_norm", "dest_key"]]
        .drop_duplicates()
        .rename(columns={"dest_key": "expected_dest_key"})
    )

    work = df_cur_des.merge(expected, on="id_origem_norm", how="left")
    df_wrong_boards = work[
        work["id_origem_norm"].astype(str).str.strip().ne("")
        & work["expected_dest_key"].notna()
        & work["dest_key"].ne(work["expected_dest_key"])
    ].copy()

    log_info(f"Wrong boards: encontrados={len(df_wrong_boards)}")
    return df_wrong_boards


def build_df_no_origin(
    df_cur_des: pd.DataFrame,
    df_or_val: pd.DataFrame,
) -> pd.DataFrame:
    if df_cur_des.empty:
        return pd.DataFrame()

    origin_ids = (
        set(df_or_val["id_origem_norm"].astype(str).str.strip())
        if not df_or_val.empty else set()
    )

    id_norm = df_cur_des["id_origem_norm"].astype(str).str.strip()
    df_no_origin = df_cur_des[
        id_norm.eq("") | ~id_norm.isin(origin_ids)
    ].copy()

    log_info(f"No origin: encontrados={len(df_no_origin)}")
    return df_no_origin
