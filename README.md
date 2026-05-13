# 🧾 AL-RH-SYNC

Pipeline automatizado para organizar a **Base RH** no Monday.com em uma estrutura de **Access Level**, garantindo que cada liderança visualize apenas os funcionários dos seus respectivos centros de custo.

---

## 🚀 O que ele faz

- Lê funcionários dos boards de origem (BASE MENSAL 2025 + 2026, escalável por ano)
- Filtra itens por departamentos válidos e mapeia cada um ao board/grupo de destino correto
- Compara origem x destino e identifica itens faltantes
- Enriquece novos itens com dados detalhados da origem
- Cria itens faltantes nos boards de destino corretos
- Detecta e remove duplicados (critério de completude de campos)
- Detecta e move itens em grupo errado (Base ↔ Desligados) — **exclusivo RH**
- Detecta e recria itens com campos críticos divergentes (salários + tipo/motivo desligamento) — **exclusivo RH**
- Detecta e remove itens em board errado e itens sem origem
- Gera resumo operacional por etapa com duração total
- Gera reconciliação final por destino (`EXPECTED_ROWS`, `ACTUAL_ROWS`, `DELTA`)

---

## 🧩 Access Level (2 de 4 pipelines)

Este pipeline é o **2/4** do projeto de níveis de acesso no Monday.com.

- Prefixo `AL` = **Access Level**
- O projeto completo é composto por 4 pipelines integrados:
  - **AFs Geradas**
  - **Base RH** ← este repositório
  - **Pagamentos Realizados**
  - **Faturamento**

---

## 🧩 Estrutura (resumida)

```bash
al_rh/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── src/
    ├── main.py
    ├── config/
    │   └── settings.py
    └── core/
        ├── utils.py
        └── monday/
            ├── execute_monday_query.py
            ├── origin/
            │   ├── fetch_origin_items.py
            │   └── enrich_origin_items.py
            └── destination/
                ├── fetch/
                │   └── fetch_destination_items.py
                ├── payload/
                │   ├── build_missing_ids.py
                │   └── build_create_payload.py
                ├── actions/
                │   ├── create_monday_items.py
                │   ├── recreate_critical_fields.py
                │   ├── duplicates/
                │   │   ├── find_duplicate_items.py
                │   │   └── delete_duplicate_items.py
                │   ├── orphans/
                │   │   ├── find_orphan_items.py
                │   │   ├── delete_wrong_board_items.py
                │   │   └── delete_no_origin_items.py
                │   ├── wrong_groups/
                │   │   ├── find_wrong_group_items.py
                │   │   └── move_wrong_group_items.py
                │   └── critical/
                │       └── find_critical_divergences.py
                └── summary/
                    └── build_execution_summary.py
```

---

## ⚙️ Configuração

Crie o arquivo `.env` com as variáveis mínimas:

```env
MONDAY_API_TOKEN=seu_token
MONDAY_BASE_URL=https://api.monday.com/v2
PIPELINE_SHOW_PROGRESS=true
```

Variáveis úteis de operação (opcionais):

```env
PIPELINE_LOG_PREFIX=[AL-RH]
MONDAY_MAX_RETRIES=5
MONDAY_REQUEST_TIMEOUT=60
MONDAY_BACKOFF_BASE=1.0
MONDAY_BACKOFF_FACTOR=2.0
MONDAY_BACKOFF_CAP=30.0
MONDAY_JITTER_MIN=0.0
MONDAY_JITTER_MAX=0.5
MONDAY_PAGE_LIMIT=500
MONDAY_ACTION_SLEEP_SECONDS=0.15
MONDAY_CREATE_SLEEP_SECONDS=0.15
```

Dry-runs por ação (default: `false`):

```env
PIPELINE_CREATE_DRY_RUN=false
PIPELINE_DELETE_DUPLICATE_DRY_RUN=false
PIPELINE_DELETE_WRONG_BOARD_DRY_RUN=false
PIPELINE_DELETE_NO_ORIGIN_DRY_RUN=false
PIPELINE_UPDATE_CRITICAL_DRY_RUN=false
PIPELINE_MOVE_WRONG_GROUPS_DRY_RUN=false
```

> Use sempre `CHAVE=valor` sem aspas e sem espaço após `=`.

---

## 🧪 Execução

### Local
```bash
python -u -m src.main
```

### Docker
```bash
docker compose up --build
```

---

## 🌬️ Airflow (produção)

- `dag_id`: `al_rh_sync`
- cron: `20 6 9-15 * *` (dias 9–15 de cada mês às 06:20, horário de Brasília)
- DAG file: `data-airflow/dags/al_rh_dag.py`

Comando da task:

```bash
docker run --rm \
  --env-file /opt/automations/al_rh/.env \
  conterp-al-rh-app:latest
```

---

## 📊 Saída operacional

O pipeline imprime:

- etapas com `CKPT START` e `CKPT END` (com duração e volume)
- DataFrames de controle por etapa
- auditoria de inconsistências:
  - duplicados
  - grupo errado (Base ↔ Desligados)
  - divergências em campos críticos
  - board errado e sem origem
- resumo final de execução (`df_summary`)
- reconciliação final por destino (`df_reconcile_by_dest`):
  - `DEST_KEY`
  - `EXPECTED_ROWS`
  - `ACTUAL_ROWS`
  - `DELTA`

---

## 🧮 Regras de negócio exclusivas do RH

- **Dois grupos por board de destino:** cada board tem `grupo_base_id` (ativos) e `grupo_desligados_id` (desligados). A função `get_target_group_id()` decide o grupo: se houver `motivo_desligamento` ou `tipo_desligamento` → Desligados; caso contrário → Base.

- **Multi-ano na origem:** `ORIGIN_BOARDS` em `settings.py` é uma lista. Para incluir 2027, basta adicionar um novo dict — sem alterar código.

- **Move Wrong Groups:** item no board correto mas no grupo errado é movido via `move_item_to_group` (não destrutivo — sem deletar e recriar).

- **Recreate Critical Fields:** campos críticos divergentes (salário base, bruto, líquido + tipo/motivo desligamento) são corrigidos via delete → reenrich da origem → create com dados corretos.

- **Destinos mapeados por departamento (`dept_keywords`):**
  - `ENEVA`
  - `FS_BIO_CPT01` — palavras-chave: FS INDUSTRIA, PERFURACAO
  - `SPTS` — palavra-chave: SPT
  - `ATP`
  - `FLUIDOS_MAR` — palavras-chave: FLUIDOS, SERGIPE MAR

---

## 🔒 Segurança

- Segredos via `.env` (não versionar)
- Execução conteinerizada
- Retry/backoff com jitter para chamadas à API do Monday
- Dry-run por tipo de ação para operações seguras
- Recomenda-se rotação periódica do token da API

---

## 🤝 Autor

**João Carser**  
[github.com/JoaoCarser](https://github.com/JoaoCarser)
