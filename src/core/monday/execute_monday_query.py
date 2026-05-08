from __future__ import annotations

import random
import time
from typing import Any, Dict, Iterable, List, Optional

import requests
from tqdm import tqdm

from src.config.settings import (
    API_URL,
    BACKOFF_FACTOR,
    BASE_DELAY,
    HEADERS,
    JITTER_MAX,
    JITTER_MIN,
    LOG_PREFIX,
    MAX_DELAY,
    MAX_RETRIES,
    PAGE_LIMIT,
    REQUEST_TIMEOUT,
    SHOW_PROGRESS,
)


def log_info(message: str) -> None:
    print(f"{LOG_PREFIX} [INFO] {message}")


def log_warn(message: str) -> None:
    print(f"{LOG_PREFIX} [WARN] {message}")


def log_error(message: str) -> None:
    print(f"{LOG_PREFIX} [ERROR] {message}")


def sleep_with_jitter(base_delay: float) -> float:
    delay = min(base_delay, MAX_DELAY)
    jitter = random.uniform(JITTER_MIN, JITTER_MAX)
    final_delay = delay + jitter
    time.sleep(final_delay)
    return final_delay


def build_backoff_delay(attempt: int) -> float:
    return min(BASE_DELAY * (BACKOFF_FACTOR ** attempt), MAX_DELAY)


def should_retry_http_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def should_retry_exception(exc: Exception) -> bool:
    return isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError))


def should_retry_graphql_errors(errors: List[Dict[str, Any]]) -> bool:
    text = str(errors).lower()
    retry_markers = [
        "complexity",
        "rate limit",
        "maxconcurrencyexceeded",
        "temporarily unavailable",
        "internal server error",
        "timeout",
        "too many requests",
    ]
    return any(marker in text for marker in retry_markers)


def format_graphql_errors(errors: List[Dict[str, Any]], max_len: int = 1800) -> str:
    return str(errors)[:max_len]


def execute_monday_query(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    operation_name: str = "graphql_request",
    timeout: int = REQUEST_TIMEOUT,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=timeout)

            if response.status_code == 200:
                result = response.json()

                if "errors" in result:
                    errors = result["errors"]
                    err_txt = format_graphql_errors(errors)

                    if "CursorExpiredError" in err_txt:
                        raise ValueError(f"{operation_name} CursorExpiredError: {err_txt}")

                    if should_retry_graphql_errors(errors) and attempt < MAX_RETRIES:
                        delay = sleep_with_jitter(build_backoff_delay(attempt))
                        log_warn(
                            f"{operation_name} GraphQL retryavel. "
                            f"Tentativa {attempt + 1}/{MAX_RETRIES}. Retry em {delay:.2f}s. "
                            f"Erro: {err_txt}"
                        )
                        continue

                    log_error(f"{operation_name} GraphQL error: {err_txt}")
                    raise ValueError(f"{operation_name} GraphQL error: {err_txt}")

                return result.get("data", {})

            if should_retry_http_status(response.status_code) and attempt < MAX_RETRIES:
                delay = sleep_with_jitter(build_backoff_delay(attempt))
                log_warn(
                    f"{operation_name} HTTP {response.status_code}. "
                    f"Tentativa {attempt + 1}/{MAX_RETRIES}. Retry em {delay:.2f}s."
                )
                continue

            log_error(f"{operation_name} HTTP {response.status_code}: {response.text[:500]}")
            response.raise_for_status()

        except Exception as exc:
            last_error = exc

            if isinstance(exc, requests.exceptions.HTTPError):
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code is not None and should_retry_http_status(status_code) and attempt < MAX_RETRIES:
                    delay = sleep_with_jitter(build_backoff_delay(attempt))
                    log_warn(
                        f"{operation_name} HTTPError {status_code}. "
                        f"Tentativa {attempt + 1}/{MAX_RETRIES}. Retry em {delay:.2f}s."
                    )
                    continue
                raise

            if should_retry_exception(exc) and attempt < MAX_RETRIES:
                delay = sleep_with_jitter(build_backoff_delay(attempt))
                log_warn(
                    f"{operation_name} {type(exc).__name__}. "
                    f"Tentativa {attempt + 1}/{MAX_RETRIES}. Retry em {delay:.2f}s."
                )
                continue

            raise

    raise RuntimeError(f"{operation_name} falhou apos retries") from last_error


def chunked(values: List[Any], size: int) -> Iterable[List[Any]]:
    for idx in range(0, len(values), size):
        yield values[idx: idx + size]


def _extract_column_maps(column_values: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for cv in column_values:
        out[cv["id"]] = {"text": cv.get("text"), "value": cv.get("value")}
    return out


def query_board_items_minimal(
    board_id: str,
    column_ids: List[str],
    limit: int = PAGE_LIMIT,
    max_cursor_restarts: int = 6,
    board_name: Optional[str] = None,
    empty_page_retries: int = 2,
) -> List[Dict[str, Any]]:
    q_initial = """
    query ($board_ids: [ID!], $limit: Int!, $column_ids: [String!]) {
      boards(ids: $board_ids) {
        items_page(limit: $limit) {
          cursor
          items {
            id
            name
            board { id }
            group { id title }
            column_values(ids: $column_ids) { id text value }
          }
        }
      }
    }
    """
    q_next = """
    query ($cursor: String!, $limit: Int!, $column_ids: [String!]) {
      next_items_page(cursor: $cursor, limit: $limit) {
        cursor
        items {
          id
          name
          board { id }
          group { id title }
          column_values(ids: $column_ids) { id text value }
        }
      }
    }
    """

    all_items_by_id: Dict[str, Dict[str, Any]] = {}
    limit = int(limit) if limit else PAGE_LIMIT
    board_label = board_name or board_id
    pbar = tqdm(
        desc=f"Board {board_label} paginas",
        unit="pag",
        dynamic_ncols=True,
        disable=not SHOW_PROGRESS,
    )

    restart = 0
    while restart <= max_cursor_restarts:
        restart += 1
        if restart > 1:
            log_warn(f"Board {board_label}: reinicio por problema de cursor ({restart - 1}/{max_cursor_restarts})")

        data = execute_monday_query(
            query=q_initial,
            variables={"board_ids": [board_id], "limit": limit, "column_ids": column_ids},
            operation_name=f"items_initial_{board_id}_r{restart}",
        )

        boards = data.get("boards", [])
        if not boards:
            break

        items_page = boards[0].get("items_page") or {}
        items = items_page.get("items", []) or []
        cursor = items_page.get("cursor")

        for it in items:
            iid = str(it.get("id", "")).strip()
            if iid:
                all_items_by_id[iid] = it
        pbar.update(1)
        pbar.set_postfix_str(f"itens_unicos={len(all_items_by_id)}")

        seen_cursors: set = set()
        needs_restart = False

        while cursor:
            if cursor in seen_cursors:
                log_warn(f"Board {board_label}: cursor repetido detectado")
                needs_restart = True
                break
            seen_cursors.add(cursor)

            try:
                page = execute_monday_query(
                    query=q_next,
                    variables={"cursor": cursor, "limit": limit, "column_ids": column_ids},
                    operation_name=f"items_next_{board_id}_r{restart}",
                ).get("next_items_page", {})
            except Exception as exc:
                if "CursorExpiredError" in str(exc):
                    needs_restart = True
                    break
                raise

            page_items = page.get("items", []) or []
            next_cursor = page.get("cursor")

            if next_cursor and len(page_items) == 0:
                recovered = False
                for retry_idx in range(empty_page_retries):
                    delay = sleep_with_jitter(build_backoff_delay(retry_idx))
                    log_warn(
                        f"Board {board_label}: pagina vazia com cursor ativo. "
                        f"retry {retry_idx + 1}/{empty_page_retries} em {delay:.2f}s"
                    )
                    retry_page = execute_monday_query(
                        query=q_next,
                        variables={"cursor": cursor, "limit": limit, "column_ids": column_ids},
                        operation_name=f"items_next_empty_retry_{board_id}_r{restart}",
                    ).get("next_items_page", {})

                    retry_items = retry_page.get("items", []) or []
                    retry_cursor = retry_page.get("cursor")
                    if retry_items:
                        page_items = retry_items
                        next_cursor = retry_cursor
                        recovered = True
                        break

                if not recovered and len(page_items) == 0:
                    log_warn(f"Board {board_label}: pagina vazia persistente. reiniciando leitura")
                    needs_restart = True
                    break

            for it in page_items:
                iid = str(it.get("id", "")).strip()
                if iid:
                    all_items_by_id[iid] = it
            pbar.update(1)
            pbar.set_postfix_str(f"itens_unicos={len(all_items_by_id)}")

            cursor = next_cursor

        if not needs_restart:
            break

    pbar.close()
    log_info(f"Board {board_label}: leitura concluida. total_itens_unicos={len(all_items_by_id)}")
    return list(all_items_by_id.values())


def query_items_by_ids(
    item_ids: List[str],
    column_ids: List[str],
    operation_name: str,
    chunk_size: int = 25,
) -> List[Dict[str, Any]]:
    if not item_ids:
        return []

    q = """
    query ($ids: [ID!], $column_ids: [String!]) {
      items(ids: $ids) {
        id
        name
        board { id }
        group { id title }
        column_values(ids: $column_ids) { id text value }
      }
    }
    """

    item_ids_unique = list(dict.fromkeys(str(x).strip() for x in item_ids if str(x).strip()))
    all_items_by_id: Dict[str, Dict[str, Any]] = {}
    chunk_size = max(1, int(chunk_size))

    for chunk in chunked(item_ids_unique, chunk_size):
        data = execute_monday_query(
            query=q,
            variables={"ids": chunk, "column_ids": column_ids},
            operation_name=operation_name,
        )
        for it in (data.get("items", []) or []):
            iid = str(it.get("id", "")).strip()
            if iid:
                all_items_by_id[iid] = it

    return list(all_items_by_id.values())
