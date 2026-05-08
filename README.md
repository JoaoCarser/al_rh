# AL-RH — Access Level · Pipeline 2/4

Pipeline de sincronização de funcionários RH do Monday.com.

Lê de **2 boards de origem** (BASE MENSAL 2025 + 2026, escalável por ano) e distribui para **5 boards de destino** por empresa. Detecta e corrige duplicados, itens em board/grupo errado, itens sem origem e campos críticos divergentes.

## Posição no Access Level

| # | Pipeline | Cor |
|---|---|---|
| 1 | AFs Geradas | Verde Neon |
| **2** | **Base RH** ← este | **Teal #00E5A0** |
| 3 | Payments | Dourado |
| 4 | Faturamento | Lilás |

## Estrutura

```
al_rh/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── src/
    ├── main.py                          # orquestrador (etapas 01–18.1)
    ├── config/settings.py               # envs, IDs, DESTINATIONS, MAPs, dry-runs
    ├── core/utils.py                    # normalize_text, _canonical_origin_id, get_dest_key...
    └── core/monday/
        ├── execute_monday_query.py      # cliente HTTP retry/backoff + paginação cursor
        ├── origin/
        │   ├── fetch_origin_items.py    → build_df_or()
        │   └── enrich_origin_items.py   → build_df_enriched()
        └── destination/
            ├── fetch/fetch_destination_items.py   → build_df_cur_des()
            ├── payload/
            │   ├── build_missing_ids.py            → filter_dept_valid(), compare_origem_destino()
            │   └── build_create_payload.py         → build_df_payload()
            ├── actions/
            │   ├── create_monday_items.py          → build_df_create_results()
            │   ├── recreate_critical_fields.py     → run_recreate_critical_fields()
            │   ├── duplicates/
            │   ├── orphans/
            │   ├── wrong_groups/                   ← exclusivo RH
            │   └── critical/                       ← exclusivo RH
            └── summary/build_execution_summary.py
```

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

| Variável | Obrigatório | Default |
|---|---|---|
| `MONDAY_API_TOKEN` | sim | — |
| `PIPELINE_CREATE_DRY_RUN` | não | false |
| `PIPELINE_DELETE_DUPLICATE_DRY_RUN` | não | false |
| `PIPELINE_DELETE_WRONG_BOARD_DRY_RUN` | não | false |
| `PIPELINE_DELETE_NO_ORIGIN_DRY_RUN` | não | false |
| `PIPELINE_UPDATE_CRITICAL_DRY_RUN` | não | false |
| `PIPELINE_MOVE_WRONG_GROUPS_DRY_RUN` | não | false |

Ver `.env.example` para lista completa.

## Execução local

```bash
python -u -m src.main
```

## Execução Docker

```bash
docker compose up --build
```

## Template Airflow (DockerOperator)

```python
from airflow.providers.docker.operators.docker import DockerOperator

al_rh = DockerOperator(
    task_id="al_rh_sync",
    image="conterp-al-rh-app:latest",
    environment={"MONDAY_API_TOKEN": "{{ var.value.MONDAY_API_TOKEN }}"},
    auto_remove=True,
    docker_url="unix://var/run/docker.sock",
)
```

## Regras de negócio exclusivas do RH

**Dois grupos por board de destino**
Cada board tem `grupo_base_id` (ativos) e `grupo_desligados_id`. A função `get_target_group_id()` decide: se houver `motivo_desligamento` ou `tipo_desligamento` → Desligados; senão → Base.

**Multi-ano na origem**
`ORIGIN_BOARDS` é uma lista. Para adicionar 2027, basta incluir novo dict em `settings.py` — sem mudar código.

**Move Wrong Groups**
Item no board certo mas grupo errado é movido via `move_item_to_group` (sem deletar/recriar).

**Recreate Critical Fields**
Campos críticos divergentes (salários + tipo/motivo desligamento) são corrigidos via delete + reenrich + create.
