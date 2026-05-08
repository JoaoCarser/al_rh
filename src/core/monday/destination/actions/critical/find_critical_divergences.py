from __future__ import annotations

from typing import Any, List

import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    COL_MOTIVO_DESLIGAMENTO_DESTINO,
    COL_SALARIO_BASE,
    COL_SALARIO_BRUTO,
    COL_TIPO_DESLIGAMENTO,
    COL_VALOR_LIQUIDO,
    LOG_PREFIX,
)
from src.core.utils import as_decimal, normalize_text


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def _is_divergent_num(a: Any, b: Any, tol: float = 0.01) -> bool:
    na = as_decimal(a)
    nb = as_decimal(b)
    if na is None and nb is None:
        return False
    if na is None or nb is None:
        return True
    return abs(float(na) - float(nb)) > tol


def _is_divergent_text(a: Any, b: Any) -> bool:
    return normalize_text(a) != normalize_text(b)


def build_df_critical_divergences(
    df_or_val: pd.DataFrame,
    df_val_base_work: pd.DataFrame,
    tol: float = 0.01,
) -> pd.DataFrame:
    if df_or_val.empty or df_val_base_work.empty:
        return pd.DataFrame()

    required_origem = {
        "origem_item_id", "name", "dest_group_id", "dest_board_id", "dest_key",
        "orig_salario_base", "orig_salario_bruto", "orig_valor_liquido",
        "motivo_desligamento", "tipo_desligamento",
    }
    required_dest = {
        "id_origem", "dest_item_id", "dest_board_id", "dest_key",
        "dest_salario_base", "dest_salario_bruto", "dest_valor_liquido",
        "motivo_desligamento", "tipo_desligamento",
    }

    if not required_origem.issubset(set(df_or_val.columns)):
        raise ValueError("df_or_val sem colunas criticas necessarias.")
    if not required_dest.issubset(set(df_val_base_work.columns)):
        raise ValueError("df_val_base_work sem colunas criticas necessarias.")

    base_dest = df_val_base_work[
        df_val_base_work["id_origem"].astype(str).str.strip() != ""
    ].copy()

    merged = df_or_val.merge(
        base_dest,
        left_on="origem_item_id",
        right_on="id_origem",
        how="inner",
        suffixes=("_orig", "_dest"),
    )
    if merged.empty:
        return pd.DataFrame()

    rows: List[dict] = []
    for _, r in tqdm(merged.iterrows(), total=len(merged), desc="Comparando campos criticos"):
        diffs = []

        if _is_divergent_text(r.get("tipo_desligamento_orig"), r.get("tipo_desligamento_dest")):
            diffs.append(COL_TIPO_DESLIGAMENTO)
        if _is_divergent_text(r.get("motivo_desligamento_orig"), r.get("motivo_desligamento_dest")):
            diffs.append(COL_MOTIVO_DESLIGAMENTO_DESTINO)
        if _is_divergent_num(r.get("orig_salario_base"), r.get("dest_salario_base"), tol=tol):
            diffs.append(COL_SALARIO_BASE)
        if _is_divergent_num(r.get("orig_salario_bruto"), r.get("dest_salario_bruto"), tol=tol):
            diffs.append(COL_SALARIO_BRUTO)
        if _is_divergent_num(r.get("orig_valor_liquido"), r.get("dest_valor_liquido"), tol=tol):
            diffs.append(COL_VALOR_LIQUIDO)

        if diffs:
            rows.append({
                "origem_item_id": str(r.get("origem_item_id", "")).strip(),
                "name": r.get("name_orig", r.get("name", "")),
                "dest_item_id": str(r.get("dest_item_id", "")).strip(),
                "dest_board_id": str(r.get("dest_board_id_dest", r.get("dest_board_id", ""))),
                "dest_key": r.get("dest_key_dest", r.get("dest_key", "")),
                "dest_group_id": r.get("dest_group_id", ""),
                "diff_cols": ", ".join(diffs),
                "orig_tipo_desligamento": r.get("tipo_desligamento_orig"),
                "dest_tipo_desligamento": r.get("tipo_desligamento_dest"),
                "orig_motivo_desligamento": r.get("motivo_desligamento_orig"),
                "dest_motivo_desligamento": r.get("motivo_desligamento_dest"),
                "orig_salario_base": r.get("orig_salario_base"),
                "dest_salario_base": r.get("dest_salario_base"),
                "orig_salario_bruto": r.get("orig_salario_bruto"),
                "dest_salario_bruto": r.get("dest_salario_bruto"),
                "orig_valor_liquido": r.get("orig_valor_liquido"),
                "dest_valor_liquido": r.get("dest_valor_liquido"),
            })

    df_divergent_items = pd.DataFrame(rows)
    log_info(f"Critical divergences: encontradas={len(df_divergent_items)}")
    return df_divergent_items
