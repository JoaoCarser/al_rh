from __future__ import annotations

import sys
import time
from typing import Any

from src.config.settings import (
    CREATE_DRY_RUN,
    DELETE_DUPLICATE_DRY_RUN,
    DELETE_NO_ORIGIN_DRY_RUN,
    DELETE_WRONG_BOARD_DRY_RUN,
    LOG_PREFIX,
    MOVE_WRONG_GROUPS_DRY_RUN,
    UPDATE_CRITICAL_DRY_RUN,
    check_required_envs,
)
from src.core.monday.destination.actions.create_monday_items import build_df_create_results
from src.core.monday.destination.actions.critical.find_critical_divergences import (
    build_df_critical_divergences,
)
from src.core.monday.destination.actions.duplicates.delete_duplicate_items import (
    run_delete_duplicate_items,
)
from src.core.monday.destination.actions.duplicates.find_duplicate_items import (
    build_df_duplicates,
)
from src.core.monday.destination.actions.orphans.delete_no_origin_items import (
    run_delete_no_origin_items,
)
from src.core.monday.destination.actions.orphans.delete_wrong_board_items import (
    run_delete_wrong_board_items,
)
from src.core.monday.destination.actions.orphans.find_orphan_items import (
    build_df_no_origin,
    build_df_wrong_boards,
)
from src.core.monday.destination.actions.recreate_critical_fields import (
    run_recreate_critical_fields,
)
from src.core.monday.destination.actions.wrong_groups.find_wrong_group_items import (
    build_df_wrong_groups,
)
from src.core.monday.destination.actions.wrong_groups.move_wrong_group_items import (
    run_move_wrong_group_items,
)
from src.core.monday.destination.fetch.fetch_destination_items import build_df_cur_des
from src.core.monday.destination.payload.build_create_payload import build_df_payload
from src.core.monday.destination.payload.build_missing_ids import (
    build_df_expected_by_dest,
    compare_origem_destino,
    filter_dept_valid,
)
from src.core.monday.destination.summary.build_execution_summary import (
    build_df_actual_by_dest,
    build_df_execution_summary,
    build_df_reconcile_by_dest,
)
from src.core.monday.origin.enrich_origin_items import build_df_enriched
from src.core.monday.origin.fetch_origin_items import build_df_or


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def log_warn(message: str) -> None:
    print(f"{LOG_PREFIX} [WARN] {message}")


def log_error(message: str) -> None:
    print(f"{LOG_PREFIX} [ERROR] {message}")


def print_stage(stage_label: str) -> None:
    print("")
    print("============================================================")
    log_info(stage_label)
    print("============================================================")
    print("")


def log_ckpt_start(step_name: str) -> float:
    log_info(f"CKPT START step={step_name}")
    return time.perf_counter()


def log_ckpt_end(step_name: str, start_perf: float, rows: Any = None) -> None:
    duration_seconds = time.perf_counter() - start_perf
    if rows is None:
        log_info(f"CKPT END step={step_name} dur_s={duration_seconds:.2f}")
        return
    log_info(f"CKPT END step={step_name} rows={rows} dur_s={duration_seconds:.2f}")


def print_df(df_name: str, df_value: Any) -> None:
    print(f"{df_name}:")
    if df_value is None:
        print("None")
        return
    try:
        print(f"rows={len(df_value)}")
    except Exception:
        pass
    if df_name in {"df_summary", "df_reconcile_by_dest"} and hasattr(df_value, "to_string"):
        print(df_value.to_string(index=False))
        return
    print(df_value)


def _remove_deleted_ids(df_work: "pd.DataFrame", df_delete_result: "pd.DataFrame") -> "pd.DataFrame":
    if df_delete_result.empty:
        return df_work
    deleted_ids = set(
        df_delete_result[df_delete_result["status"] == "deleted"]["dest_item_id"].astype(str)
    )
    if not deleted_ids:
        return df_work
    return df_work[~df_work["dest_item_id"].astype(str).isin(deleted_ids)].copy()


def main() -> int:
    pipeline_start_ts = time.time()

    try:
        log_info("Iniciando pipeline AL-RH")

        # ------------------------------------------------------------------
        print_stage("ETAPA 01 - VALIDAR AMBIENTE")
        stage_perf = log_ckpt_start("check_env")
        check_required_envs()
        log_ckpt_end("check_env", stage_perf)

        # ------------------------------------------------------------------
        print_stage("ETAPA 02 - LER ORIGEM (BASE MENSAL 2025 + 2026)")
        stage_perf = log_ckpt_start("read_origin")
        df_or = build_df_or()
        print_df("df_or", df_or)
        log_ckpt_end("read_origin", stage_perf, len(df_or))

        # ------------------------------------------------------------------
        print_stage("ETAPA 03 - LER DESTINOS (5 BOARDS RH)")
        stage_perf = log_ckpt_start("read_destination")
        df_cur_des = build_df_cur_des()
        print_df("df_cur_des", df_cur_des)
        log_ckpt_end("read_destination", stage_perf, len(df_cur_des))

        # ------------------------------------------------------------------
        print_stage("ETAPA 04 - FILTRAR DEPARTAMENTOS VALIDOS")
        stage_perf = log_ckpt_start("filter_dept_valid")
        df_or_val = filter_dept_valid(df_or)
        print_df("df_or_val", df_or_val)
        log_ckpt_end("filter_dept_valid", stage_perf, len(df_or_val))

        # ------------------------------------------------------------------
        print_stage("ETAPA 04.1 - EXPECTED POR DESTINO")
        stage_perf = log_ckpt_start("expected_by_dest")
        df_expected_by_dest = build_df_expected_by_dest(df_or_val)
        print_df("df_expected_by_dest", df_expected_by_dest)
        log_ckpt_end("expected_by_dest", stage_perf, len(df_expected_by_dest))

        # ------------------------------------------------------------------
        print_stage("ETAPA 05 - COMPARE ORIGEM X DESTINO")
        stage_perf = log_ckpt_start("compare_origem_destino")
        df_new_items, df_existing = compare_origem_destino(df_or_val, df_cur_des)
        print_df("df_new_items", df_new_items)
        print_df("df_existing", df_existing)
        log_ckpt_end("compare_origem_destino", stage_perf, len(df_new_items))

        # ------------------------------------------------------------------
        print_stage("ETAPA 06 - ENRICH NOVOS ITENS")
        stage_perf = log_ckpt_start("enrich_origin")
        df_to_create_raw, df_to_create_view, df_enrich_missing = build_df_enriched(df_new_items)
        print_df("df_to_create_view", df_to_create_view)
        if not df_enrich_missing.empty:
            log_warn(f"Enrich: {len(df_enrich_missing)} itens sem dados na origem.")
            print_df("df_enrich_missing", df_enrich_missing)
        log_ckpt_end("enrich_origin", stage_perf, len(df_to_create_raw))

        # ------------------------------------------------------------------
        print_stage("ETAPA 07 - BUILD PAYLOAD")
        stage_perf = log_ckpt_start("build_payload")
        df_payload_ready = build_df_payload(df_to_create_raw)
        print_df("df_payload_ready", df_payload_ready)
        log_ckpt_end("build_payload", stage_perf, len(df_payload_ready))

        # ------------------------------------------------------------------
        print_stage("ETAPA 08 - CREATE ITENS NOS DESTINOS")
        stage_perf = log_ckpt_start("create_destination_items")
        df_create_result, df_create_board_summary = build_df_create_results(
            df_payload_ready,
            dry_run=CREATE_DRY_RUN,
        )
        print_df("df_create_result", df_create_result)
        print_df("df_create_board_summary", df_create_board_summary)
        log_ckpt_end("create_destination_items", stage_perf, len(df_create_result))

        # ------------------------------------------------------------------
        print_stage("ETAPA 09 - RELOAD DESTINOS (POS-CREATE)")
        stage_perf = log_ckpt_start("reload_destination")
        df_val_base = build_df_cur_des()
        df_val_base_work = df_val_base.copy()
        print_df("df_val_base", df_val_base)
        log_ckpt_end("reload_destination", stage_perf, len(df_val_base))

        # ------------------------------------------------------------------
        print_stage("ETAPA 10 - DETECTAR DUPLICADOS")
        stage_perf = log_ckpt_start("detect_duplicates")
        df_dup_delete = build_df_duplicates(df_val_base_work)
        print_df("df_dup_delete", df_dup_delete)
        log_ckpt_end("detect_duplicates", stage_perf, len(df_dup_delete))

        # ------------------------------------------------------------------
        print_stage("ETAPA 11 - DELETE DUPLICADOS")
        stage_perf = log_ckpt_start("delete_duplicates")
        df_delete_duplicates_result = run_delete_duplicate_items(
            df_dup_delete,
            dry_run=DELETE_DUPLICATE_DRY_RUN,
        )
        print_df("df_delete_duplicates_result", df_delete_duplicates_result)
        df_val_base_work = _remove_deleted_ids(df_val_base_work, df_delete_duplicates_result)
        log_ckpt_end("delete_duplicates", stage_perf, len(df_delete_duplicates_result))

        # ------------------------------------------------------------------
        print_stage("ETAPA 12 - DETECTAR WRONG GROUPS [EXCLUSIVO RH]")
        stage_perf = log_ckpt_start("detect_wrong_groups")
        df_wrong_groups = build_df_wrong_groups(df_val_base_work, df_or_val)
        print_df("df_wrong_groups", df_wrong_groups)
        log_ckpt_end("detect_wrong_groups", stage_perf, len(df_wrong_groups))

        # ------------------------------------------------------------------
        print_stage("ETAPA 13 - MOVE WRONG GROUPS [EXCLUSIVO RH]")
        stage_perf = log_ckpt_start("move_wrong_groups")
        df_move_wrong_groups_result = run_move_wrong_group_items(
            df_wrong_groups,
            dry_run=MOVE_WRONG_GROUPS_DRY_RUN,
        )
        print_df("df_move_wrong_groups_result", df_move_wrong_groups_result)
        if not df_move_wrong_groups_result.empty:
            moved_ids = set(
                df_move_wrong_groups_result[
                    df_move_wrong_groups_result["status"] == "moved"
                ]["dest_item_id"].astype(str)
            )
            if moved_ids:
                move_map = (
                    df_wrong_groups[["dest_item_id", "expected_group_id"]]
                    .drop_duplicates()
                    .set_index("dest_item_id")["expected_group_id"]
                    .to_dict()
                )

                def _apply_group(row) -> str:
                    iid = str(row.get("dest_item_id", "")).strip()
                    if iid in moved_ids:
                        return str(move_map.get(iid, row.get("dest_group_id", ""))).strip()
                    return str(row.get("dest_group_id", "")).strip()

                df_val_base_work["dest_group_id"] = df_val_base_work.apply(_apply_group, axis=1)
        log_ckpt_end("move_wrong_groups", stage_perf, len(df_move_wrong_groups_result))

        # ------------------------------------------------------------------
        print_stage("ETAPA 14 - DETECTAR DIVERGENCIAS CRITICAS [EXCLUSIVO RH]")
        stage_perf = log_ckpt_start("detect_critical_divergences")
        df_divergent_items = build_df_critical_divergences(df_or_val, df_val_base_work, tol=0.01)
        print_df("df_divergent_items", df_divergent_items)
        log_ckpt_end("detect_critical_divergences", stage_perf, len(df_divergent_items))

        # ------------------------------------------------------------------
        print_stage("ETAPA 15 - RECREATE CRITICAL FIELDS [EXCLUSIVO RH]")
        stage_perf = log_ckpt_start("recreate_critical_fields")
        (
            df_to_recreate_delete,
            df_recreate_delete_result,
            df_recreate_seed,
            df_recreate_create_result,
            df_recreate_missing,
        ) = run_recreate_critical_fields(
            df_divergent_items,
            df_or_val,
            dry_run=UPDATE_CRITICAL_DRY_RUN,
        )
        print_df("df_recreate_delete_result", df_recreate_delete_result)
        print_df("df_recreate_create_result", df_recreate_create_result)
        if not df_recreate_missing.empty:
            log_warn(f"Recreate: {len(df_recreate_missing)} itens sem dados na origem.")
            print_df("df_recreate_missing", df_recreate_missing)
        log_ckpt_end("recreate_critical_fields", stage_perf, len(df_divergent_items))

        # ------------------------------------------------------------------
        print_stage("ETAPA 16 - DETECTAR ORPHANS (WRONG BOARDS + NO ORIGIN)")
        stage_perf = log_ckpt_start("detect_orphans")
        df_wrong_boards = build_df_wrong_boards(df_val_base_work, df_or_val)
        df_no_origin = build_df_no_origin(df_val_base_work, df_or_val)
        print_df("df_wrong_boards", df_wrong_boards)
        print_df("df_no_origin", df_no_origin)
        log_ckpt_end("detect_orphans", stage_perf, len(df_wrong_boards) + len(df_no_origin))

        # ------------------------------------------------------------------
        print_stage("ETAPA 17 - DELETE ORPHANS")
        stage_perf = log_ckpt_start("delete_orphans")
        df_delete_wrong_boards_result = run_delete_wrong_board_items(
            df_wrong_boards,
            dry_run=DELETE_WRONG_BOARD_DRY_RUN,
        )
        df_val_base_work = _remove_deleted_ids(df_val_base_work, df_delete_wrong_boards_result)

        df_delete_no_origin_result = run_delete_no_origin_items(
            df_no_origin,
            dry_run=DELETE_NO_ORIGIN_DRY_RUN,
        )
        df_val_base_work = _remove_deleted_ids(df_val_base_work, df_delete_no_origin_result)

        print_df("df_delete_wrong_boards_result", df_delete_wrong_boards_result)
        print_df("df_delete_no_origin_result", df_delete_no_origin_result)
        log_ckpt_end(
            "delete_orphans",
            stage_perf,
            len(df_delete_wrong_boards_result) + len(df_delete_no_origin_result),
        )

        # ------------------------------------------------------------------
        print_stage("ETAPA 18 - RESUMO FINAL")
        stage_perf = log_ckpt_start("build_summary")
        df_summary = build_df_execution_summary(
            pipeline_start_ts=pipeline_start_ts,
            df_create_result=df_create_result,
            df_recreate_create_result=df_recreate_create_result,
            df_divergent_items=df_divergent_items,
            df_delete_duplicates_result=df_delete_duplicates_result,
            df_delete_wrong_boards_result=df_delete_wrong_boards_result,
            df_delete_no_origin_result=df_delete_no_origin_result,
            df_move_wrong_groups_result=df_move_wrong_groups_result,
        )
        print_df("df_summary", df_summary)
        log_ckpt_end("build_summary", stage_perf, len(df_summary))

        # ------------------------------------------------------------------
        print_stage("ETAPA 18.1 - RECONCILIACAO POR DESTINO")
        stage_perf = log_ckpt_start("reconcile_by_dest")
        df_destino_final = build_df_cur_des()
        df_actual_by_dest = build_df_actual_by_dest(df_destino_final)
        df_reconcile_by_dest = build_df_reconcile_by_dest(df_expected_by_dest, df_actual_by_dest)
        print_df("df_reconcile_by_dest", df_reconcile_by_dest)
        log_ckpt_end("reconcile_by_dest", stage_perf, len(df_reconcile_by_dest))

        # ------------------------------------------------------------------
        print_stage("Pipeline AL-RH concluido com sucesso")
        return 0

    except Exception as exc:
        log_error(f"Falha na execucao do pipeline: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
