from __future__ import annotations

import pandas as pd

from src.config.settings import DESTINATIONS, LOG_PREFIX


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def build_df_wrong_groups(
    df_val_base_work: pd.DataFrame,
    df_or_val: pd.DataFrame,
) -> pd.DataFrame:
    if df_val_base_work.empty or df_or_val.empty:
        return pd.DataFrame()

    required_origem = {"id_origem_norm", "dest_board_id", "dest_group_id"}
    required_dest = {"id_origem_norm", "dest_board_id", "dest_item_id", "dest_key"}

    if not required_origem.issubset(set(df_or_val.columns)):
        raise ValueError("df_or_val sem colunas necessarias para wrong-group")
    if not required_dest.issubset(set(df_val_base_work.columns)):
        raise ValueError("df_val_base_work sem colunas necessarias para wrong-group")

    expected = (
        df_or_val[["id_origem_norm", "dest_board_id", "dest_group_id"]]
        .drop_duplicates()
        .rename(columns={"dest_group_id": "expected_group_id"})
    )

    work = df_val_base_work.copy()
    work["id_origem_norm"] = work["id_origem_norm"].astype(str).str.strip()
    work["dest_board_id"] = work["dest_board_id"].astype(str).str.strip()

    if "dest_group_id" not in work.columns:
        def _derive_group_id(row: pd.Series) -> str:
            dest_key = str(row.get("dest_key", "")).strip()
            title = str(row.get("dest_group_title", "")).strip().upper()
            cfg = DESTINATIONS.get(dest_key, {})
            if title == "DESLIGADOS":
                return str(cfg.get("grupo_desligados_id", "")).strip()
            if title == "BASE":
                return str(cfg.get("grupo_base_id", "")).strip()
            return ""

        work["dest_group_id"] = work.apply(_derive_group_id, axis=1)
    else:
        work["dest_group_id"] = work["dest_group_id"].astype(str).str.strip()

    merged = work.merge(expected, on=["id_origem_norm", "dest_board_id"], how="left")

    df_wrong_groups = merged[
        merged["id_origem_norm"].ne("")
        & merged["expected_group_id"].notna()
        & merged["expected_group_id"].astype(str).str.strip().ne("")
        & merged["dest_group_id"].ne(merged["expected_group_id"].astype(str).str.strip())
    ].copy()

    log_info(f"Wrong groups: encontrados={len(df_wrong_groups)}")
    return df_wrong_groups
