# Databricks notebook source
# DBTITLE 1,Widgets
dbutils.widgets.text("catalog", "main", "1. Catalog")
dbutils.widgets.text("schema", "geo_fraud_lab", "2. Schema")

# COMMAND ----------

# DBTITLE 1,Config
catalog = dbutils.widgets.get("catalog")
schema  = dbutils.widgets.get("schema")
print(f"Target: {catalog}.{schema}")

# COMMAND ----------

# DBTITLE 1,Auto-discover SQL warehouse (serverless / Photon preferred)
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

def _pick_warehouse(client):
    all_wh = list(client.warehouses.list())
    # Prefer serverless, then Photon, then any running warehouse
    for wh in all_wh:
        if getattr(wh, "enable_serverless_compute", False) and wh.state and wh.state.value == "RUNNING":
            return wh.id
    for wh in all_wh:
        if "photon" in (wh.cluster_size or "").lower() and wh.state and wh.state.value == "RUNNING":
            return wh.id
    for wh in all_wh:
        if wh.state and wh.state.value == "RUNNING":
            return wh.id
    # Fall back to first warehouse (will start on first query)
    if all_wh:
        return all_wh[0].id
    return None

warehouse_id = _pick_warehouse(w)
if not warehouse_id:
    raise RuntimeError("No SQL warehouses found in this workspace. Create one and retry.")
print(f"Using warehouse: {warehouse_id}")

# COMMAND ----------

# DBTITLE 1,SQL splitter — respects $$ ... $$ blocks (metric view YAML)
def split_statements(text):
    """Split on ; but never inside $$....$$ dollar-quoted blocks."""
    stmts, buf, in_dollar = [], [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        if '$$' in line:
            in_dollar = (in_dollar != (line.count('$$') % 2 == 1))
        buf.append(line)
        if not in_dollar and line.rstrip().endswith(';'):
            chunk = '\n'.join(buf).strip().rstrip(';').strip()
            if chunk:
                stmts.append(chunk)
            buf = []
    tail = '\n'.join(buf).strip().rstrip(';').strip()
    if tail:
        stmts.append(tail)
    return stmts

# COMMAND ----------

# DBTITLE 1,Fetch SQL files from GitHub and execute via Statement Execution API
import urllib.request
from databricks.sdk.service.sql import StatementState

BASE_URL = "https://raw.githubusercontent.com/danteliew6/geo-fraud-lab/main"

SQL_FILES = [
    "sql/01_tables_and_comments.sql",
    "sql/02_dim_province.sql",
    "sql/03_fraud_geo_views.sql",
    "sql/04_metric_base.sql",
    "sql/05_metric_view.sql",
    "sql/06_geo_analysis_views.sql",
    "sql/07_looker_views.sql",
]

def fetch_sql(path):
    url = f"{BASE_URL}/{path}"
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")

def execute_sql(stmt, wh_id, cat, sch):
    result = w.statement_execution.execute_statement(
        warehouse_id=wh_id,
        statement=stmt,
        catalog=cat,
        schema=sch,
        wait_timeout="120s",
    )
    if result.status.state not in (StatementState.SUCCEEDED,):
        err = result.status.error
        raise RuntimeError(f"Statement failed ({result.status.state}): {err}")
    return result

total_files = len(SQL_FILES)
for file_idx, sql_path in enumerate(SQL_FILES, 1):
    print(f"\n[{file_idx}/{total_files}] {sql_path}")
    sql_text = fetch_sql(sql_path)
    sql_text = sql_text.replace("{{CATALOG}}", catalog).replace("{{SCHEMA}}", schema)

    statements = split_statements(sql_text)
    print(f"  {len(statements)} statement(s) found")

    ok = 0
    for stmt_idx, stmt in enumerate(statements, 1):
        try:
            execute_sql(stmt, warehouse_id, catalog, schema)
            ok += 1
            print(f"  [{stmt_idx}/{len(statements)}] OK")
        except Exception as e:
            print(f"  [{stmt_idx}/{len(statements)}] FAILED: {e}")
            print(f"  Statement preview: {stmt[:200]}")
            raise

    print(f"  Done: {ok} statement(s) succeeded")

print("\nAll SQL layers applied successfully")
