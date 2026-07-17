# Databricks notebook source
# DBTITLE 1,Widgets
dbutils.widgets.text("catalog", "workspace", "1. Catalog")
dbutils.widgets.text("schema", "geo_fraud_lab", "2. Schema")
dbutils.widgets.text("sql_path", "", "3. Bundle files root (set by DAB)")

# COMMAND ----------

# DBTITLE 1,Config
catalog  = dbutils.widgets.get("catalog")
schema   = dbutils.widgets.get("schema")
sql_path = dbutils.widgets.get("sql_path")
print(f"Target: {catalog}.{schema}")

# COMMAND ----------

# DBTITLE 1,Locate the bundled sql/ directory
# The DAB syncs the whole repo into the workspace and passes its root as sql_path.
# We read the SQL layers straight from there — no GitHub fetch, no SQL warehouse.
# When run outside a bundle (e.g. cloned into the workspace), fall back to a path
# relative to this notebook.
import os

def _resolve_sql_dir(root: str) -> str:
    candidates = []
    if root:
        candidates += [os.path.join(root, "sql"), root]
    # Notebook lives in <repo>/notebooks; sql/ is a sibling.
    try:
        nb_dir = os.path.dirname(
            dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
        )
        candidates.append("/Workspace" + os.path.join(os.path.dirname(nb_dir), "sql"))
    except Exception:
        pass
    for c in candidates:
        if os.path.isdir(c):
            return c
    raise FileNotFoundError(
        f"Could not locate the sql/ directory. Tried: {candidates}"
    )

sql_dir = _resolve_sql_dir(sql_path)
print(f"Reading SQL from: {sql_dir}")

# COMMAND ----------

# DBTITLE 1,SQL splitter — respects $$ ... $$ blocks (metric view YAML)
def split_statements(text):
    """Split on ; but never inside $$....$$ dollar-quoted blocks (metric-view YAML)."""
    stmts, buf, in_dollar = [], [], False
    for line in text.splitlines():
        if line.strip().startswith('--'):
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

# DBTITLE 1,Execute SQL layers on serverless (H3 + ST_ + Metric Views are native here)
SQL_FILES = [
    "01_tables_and_comments.sql",
    "02_dim_province.sql",
    "03_fraud_geo_views.sql",
    "04_metric_base.sql",
    "05_metric_view.sql",
    "06_geo_analysis_views.sql",
    "07_looker_views.sql",
]

total_files = len(SQL_FILES)
for file_idx, fname in enumerate(SQL_FILES, 1):
    print(f"\n[{file_idx}/{total_files}] {fname}")
    with open(os.path.join(sql_dir, fname), "r") as f:
        sql_text = f.read()
    sql_text = sql_text.replace("{{CATALOG}}", catalog).replace("{{SCHEMA}}", schema)

    statements = split_statements(sql_text)
    print(f"  {len(statements)} statement(s) found")

    for stmt_idx, stmt in enumerate(statements, 1):
        try:
            spark.sql(stmt)
            print(f"  [{stmt_idx}/{len(statements)}] OK")
        except Exception as e:
            print(f"  [{stmt_idx}/{len(statements)}] FAILED: {e}")
            print(f"  Statement preview: {stmt[:200]}")
            raise

print("\nAll SQL layers applied successfully")

# COMMAND ----------

# DBTITLE 1,Verify
with open(os.path.join(sql_dir, "08_verify_all.sql"), "r") as f:
    verify_sql = f.read().replace("{{CATALOG}}", catalog).replace("{{SCHEMA}}", schema)

for stmt in split_statements(verify_sql):
    display(spark.sql(stmt))

print(f"\nLab installed into {catalog}.{schema}")
