from __future__ import annotations

import pandas as pd

from src.core.monday.destination.actions.duplicates.delete_duplicate_items import _run_delete


def run_delete_wrong_board_items(df_wrong_boards: pd.DataFrame, dry_run: bool = True) -> pd.DataFrame:
    return _run_delete(df_wrong_boards, reason="wrong_boards", dry_run=dry_run)
