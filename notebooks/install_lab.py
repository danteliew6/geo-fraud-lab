# Databricks notebook source
# MAGIC %md
# MAGIC # Geo Fraud Lab — One-Click Installer
# MAGIC Run all cells top to bottom. That's it.
# MAGIC
# MAGIC **What this does:**
# MAGIC 1. Downloads SQL files + the data generator from GitHub
# MAGIC 2. Generates ~20k customers, ~30k loan applications, ~18k loans, ~200k repayments
# MAGIC 3. Builds the full gold star schema with H3 geospatial index, fraud-signal views, and a governed Metric View
# MAGIC 4. Prints a verification summary
# MAGIC
# MAGIC **Requirements:** Unity Catalog enabled
# MAGIC
# MAGIC ⚠️ Cluster requirement: Run this notebook on a **Serverless cluster** or **DBR 17.3+ LTS** cluster.
# MAGIC ST_ geospatial functions and Metric Views are not available on older runtimes.

# COMMAND ----------

# DBTITLE 1,Step 1: Configure (fill in the widgets, then Run All)
dbutils.widgets.text("catalog",             "main",          "1. Your catalog (must exist)")
dbutils.widgets.text("schema",              "geo_fraud_lab", "2. Schema to create")

# COMMAND ----------

# DBTITLE 1,Step 2: Validate config
catalog            = dbutils.widgets.get("catalog")
schema             = dbutils.widgets.get("schema")

if not catalog:
    raise ValueError("❌ Please set 'Your catalog' widget above and click Run All.")

print(f"✅ Target: {catalog}.{schema}")

# COMMAND ----------

# DBTITLE 1,Step 3: Install pandas/numpy (if not available) and download files from GitHub
import subprocess, sys

# pandas + numpy are pre-installed on DBR clusters; this is a safety net for
# minimal environments (e.g. single-node serverless notebooks).
try:
    import pandas, numpy
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pandas", "numpy"])

import urllib.request, pathlib

BASE = "https://raw.githubusercontent.com/danteliew6/geo-fraud-lab/main"
TMP  = pathlib.Path("/tmp/geo_fraud_lab")
TMP.mkdir(parents=True, exist_ok=True)

SQL_FILES = [
    "sql/01_tables_and_comments.sql",
    "sql/02_dim_province.sql",
    "sql/03_fraud_geo_views.sql",
    "sql/04_metric_base.sql",
    "sql/05_metric_view.sql",
    "sql/06_geo_analysis_views.sql",
    "sql/07_looker_views.sql",
    "sql/08_verify_all.sql",
]

for f in SQL_FILES:
    dest = TMP / pathlib.Path(f).name
    urllib.request.urlretrieve(f"{BASE}/{f}", dest)
    print(f"  ✅ Downloaded {f}")

urllib.request.urlretrieve(f"{BASE}/scripts/generate_data.py", TMP / "generate_data.py")
print("  ✅ Downloaded generate_data.py")

# COMMAND ----------

# DBTITLE 1,Step 4: Create schema
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
print(f"✅ Schema {catalog}.{schema} ready")

# COMMAND ----------

# DBTITLE 1,Step 5: Generate synthetic dataset and write tables
sys.path.insert(0, str(TMP))
import importlib

# Fresh import in case the cell is re-run
if "generate_data" in sys.modules:
    importlib.reload(sys.modules["generate_data"])
import generate_data

print("📊 Generating synthetic lending + fraud dataset (fixed seed — same data for everyone)...")
tables = generate_data.generate()
generate_data.summarize(tables)

print("\n📥 Writing tables to Unity Catalog...")
for table_name, df in tables.items():
    spark_df = spark.createDataFrame(df)
    full_name = f"{catalog}.{schema}.{table_name}"
    spark_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(full_name)
    print(f"  ✅ {full_name}: {len(df):,} rows")

print("✅ Base tables written")

# COMMAND ----------

# DBTITLE 1,Step 6: Build H3 index, views, and metric view via SQL
import re

# SQL files in execution order (08_verify_all is skipped here; run separately below)
sql_run_files = [
    "01_tables_and_comments.sql",
    "02_dim_province.sql",
    "03_fraud_geo_views.sql",
    "04_metric_base.sql",
    "05_metric_view.sql",
    "06_geo_analysis_views.sql",
    "07_looker_views.sql",
]

total = len(sql_run_files)
for i, fname in enumerate(sql_run_files, 1):
    sql_file = TMP / fname
    sql_text = sql_file.read_text()
    sql_text = sql_text.replace("{{CATALOG}}", catalog).replace("{{SCHEMA}}", schema)

    # Split on semicolons, skip blank/comment-only chunks
    statements = [s.strip() for s in sql_text.split(";") if re.sub(r"--[^\n]*", "", s).strip()]
    ok = 0
    for stmt in statements:
        try:
            spark.sql(stmt)
            ok += 1
        except Exception as e:
            print(f"  ⚠️  {fname} stmt {ok+1}: {e}")
            raise
    print(f"  ✅ Step {i}/{total}: {fname} ({ok} statement{'s' if ok != 1 else ''})")

print("✅ All SQL layers applied")

# COMMAND ----------

# DBTITLE 1,Step 7: Verify
print("🔍 Verification\n")

core_tables = [
    "dim_customer",
    "dim_province",
    "dim_product",
    "dim_date",
    "fact_loan_application",
    "fact_loan",
    "fact_repayment",
]
for table in core_tables:
    try:
        n = spark.sql(f"SELECT COUNT(*) AS n FROM {catalog}.{schema}.{table}").collect()[0]["n"]
        status = "✅" if n > 0 else "❌ EMPTY"
        print(f"  {status}  {table}: {n:,} rows")
    except Exception as e:
        print(f"  ❌  {table}: {e}")

views = [
    "vw_fraud_signals",
    "vw_fraud_hotspots",
    "vw_geo_distance_bands",
    "vw_ls_portfolio_overview",
    "vw_ls_fraud_hotspots",
]
print()
for view in views:
    try:
        n = spark.sql(f"SELECT COUNT(*) AS n FROM {catalog}.{schema}.{view}").collect()[0]["n"]
        status = "✅" if n > 0 else "❌ EMPTY"
        print(f"  {status}  {view}: {n:,} rows")
    except Exception as e:
        print(f"  ❌  {view}: {e}")

print()
try:
    result = spark.sql(f"""
        SELECT MEASURE(fraud_rate) AS fraud_rate, MEASURE(npl_ratio) AS npl_ratio
        FROM {catalog}.{schema}.metrics_lending
        LIMIT 1
    """).collect()
    if result:
        print(f"  ✅  metrics_lending: fraud_rate={result[0]['fraud_rate']:.1%}, npl_ratio={result[0]['npl_ratio']:.1%}")
    else:
        print("  ⚠️  metrics_lending: no rows returned")
except Exception as e:
    print(f"  ⚠️  metrics_lending (metric view): {e}")
    print("     (If this fails, the metric view may need a DBR 17.3+ cluster — all other objects are fine)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Lab installed!
# MAGIC
# MAGIC **Your schema:** `{catalog}.{schema}` (substitute your actual values above)
# MAGIC
# MAGIC ### What was built
# MAGIC | Layer | Objects |
# MAGIC |---|---|
# MAGIC | Gold star schema | `dim_customer`, `dim_province`, `dim_product`, `dim_date`, `fact_loan_application`, `fact_loan`, `fact_repayment` |
# MAGIC | Fraud-signal views | `vw_fraud_signals` (impossible travel, location mismatch, device rings, foreign IP), `vw_fraud_hotspots` (H3 cell aggregation) |
# MAGIC | Geospatial views | `vw_geo_hotspots_kring`, `vw_geo_province_choropleth`, `vw_geo_distance_bands`, `vw_geo_device_ring_clusters` |
# MAGIC | Metric View | `metrics_lending` — fraud rate, NPL ratio, PAR30, approval rate, disbursed IDR, active borrowers |
# MAGIC | Looker Studio views | `vw_ls_portfolio_overview`, `vw_ls_disbursement_by_month`, `vw_ls_portfolio_by_province`, `vw_ls_fraud_by_province`, `vw_ls_fraud_hotspots`, `vw_ls_hotspots_kring`, `vw_ls_distance_bands`, `vw_ls_fraud_rings`, `vw_ls_impossible_travel`, `vw_ls_fraud_by_month` |
# MAGIC
# MAGIC ### What was deployed
# MAGIC | Item | Details |
# MAGIC |---|---|
# MAGIC | AI/BI Dashboard | **Geo Fraud Command Center** — auto-deployed; URL printed at the end of Run All |
# MAGIC
# MAGIC ### Next steps
# MAGIC - Open the **AI/BI Dashboard** link printed at the end of Run All.
# MAGIC - Connect **Looker Studio** (or any BI tool) to your workspace SQL warehouse and point it at the schema above.
# MAGIC - See [`docs/looker_studio_integration.md`](https://github.com/danteliew6/geo-fraud-lab/blob/main/docs/looker_studio_integration.md) for step-by-step setup.
# MAGIC - Explore fraud signals: `SELECT * FROM {catalog}.{schema}.vw_fraud_signals LIMIT 100`

# COMMAND ----------

# DBTITLE 1,Step 8: Deploy AI/BI Dashboards
# The dashboard JSON files use bare table names (catalog/schema are supplied by the
# DAB at deploy time). For the notebook path we qualify them here so the datasets
# resolve, then create + publish each dashboard via the Lakeview API.
dashboard_urls = {}
try:
    from databricks.sdk import WorkspaceClient
    import urllib.request, re

    _DASHBOARDS = [
        ("dashboards/geo_fraud.lvdash.json",    "Geo Fraud Command Center"),
        ("dashboards/tunaiku_c360.lvdash.json", "Tunaiku Lending 360"),
    ]

    _w = WorkspaceClient()
    # Auto-detect a warehouse (serverless preferred) to back the dashboards.
    try:
        _wh_id = next(
            (wh.id for wh in _w.warehouses.list() if getattr(wh, 'enable_serverless_compute', False)),
            next((wh.id for wh in _w.warehouses.list()), None)
        )
    except Exception:
        _wh_id = None

    _workspace_host = spark.conf.get("spark.databricks.workspaceUrl")

    # Idempotency: map existing ACTIVE dashboards by display name so re-running
    # the notebook UPDATES in place instead of spawning duplicate dashboards.
    _existing = {}
    try:
        for _d in _w.lakeview.list():
            if getattr(_d, "lifecycle_state", "ACTIVE") == "ACTIVE" and _d.display_name:
                _existing.setdefault(_d.display_name, _d.dashboard_id)
    except Exception:
        pass

    for _path, _name in _DASHBOARDS:
        try:
            with urllib.request.urlopen(f"{BASE}/{_path}") as _r:
                _spec = _r.read().decode()
            # Dataset queries are hard-coded to the 'geo_fraud_lab' schema. Point them
            # at the notebook's actual schema, then prepend the catalog so they become
            # <catalog>.<schema>.<table> (dashboard.yml handles this for the DAB path).
            if schema != "geo_fraud_lab":
                _spec = re.sub(r"(FROM|JOIN)\s+geo_fraud_lab\.",
                               lambda m: f"{m.group(1)} {schema}.", _spec)
            _spec = re.sub(rf"(FROM|JOIN)\s+{re.escape(schema)}\.",
                           lambda m: f"{m.group(1)} {catalog}.{schema}.", _spec)

            _existing_id = _existing.get(_name)
            if _existing_id:
                _dash = _w.lakeview.update(
                    dashboard_id=_existing_id,
                    serialized_dashboard=_spec,
                    display_name=_name,
                    warehouse_id=_wh_id,
                )
                _verb = "updated"
            else:
                _dash = _w.lakeview.create(
                    serialized_dashboard=_spec,
                    display_name=_name,
                    warehouse_id=_wh_id,
                )
                _verb = "created"
            _w.lakeview.publish(dashboard_id=_dash.dashboard_id, warehouse_id=_wh_id)
            _url = f"https://{_workspace_host}/dashboardsv3/{_dash.dashboard_id}/published"
            dashboard_urls[_name] = _url
            print(f"✅ Dashboard {_verb}: {_name} → {_url}")
        except Exception as _e:
            print(f"⚠️ Dashboard '{_name}' deploy failed: {_e}")
except Exception as _e:
    print(f"⚠️ Dashboard deploy step failed: {_e}")
    print("   (Tables and views are installed — deploy the dashboards manually via the Databricks UI)")

# COMMAND ----------

print(f"✅ Schema: {catalog}.{schema}")
for _name, _url in dashboard_urls.items():
    print(f"  AI/BI Dashboard — {_name}: {_url}")
