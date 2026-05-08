from __future__ import annotations

import pandas as pd

from src.core.monday.destination.actions.duplicates.delete_duplicate_items import _run_delete


def run_delete_no_origin_items(df_no_origin: pd.DataFrame, dry_run: bool = True) -> pd.DataFrame:
    return _run_delete(df_no_origin, reason="no_origin", dry_run=dry_run)
