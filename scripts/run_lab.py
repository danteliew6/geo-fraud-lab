#!/usr/bin/env python3
"""
geo-fraud-lab — end-to-end installer.

Runs the whole lab into ANY Unity Catalog schema:
  1. generate deterministic synthetic data (scripts/generate_data.py)
  2. write the GOLD star-schema tables to <catalog>.<schema>
  3. execute the SQL layers in order (tables -> geo/fraud views -> metric view
     -> geospatial analysis views -> Looker Studio views)
  4. verify every object and print a row-count report

Runs in two environments with the same code:
  * Local / CI (default)  : writes tables via Databricks Connect (serverless),
                            executes SQL via the Statement Execution API on a
                            serverless/Photon SQL warehouse (H3 + ST_ functions).
  * Inside a Databricks job: uses the ambient Spark session for the writes and
                            the job's own credentials for SQL execution.

All identifiers are parameterized — nothing about any specific workspace is
hard-coded. Configuration comes from CLI flags or environment variables:

  --catalog / GEO_FRAUD_CATALOG
  --schema  / GEO_FRAUD_SCHEMA           (default: geo_fraud_lab)
  --warehouse-id / GEO_FRAUD_WAREHOUSE_ID
  --profile / DATABRICKS_PROFILE         (local auth; omit inside a job)

The SQL files use the tokens {{CATALOG}} and {{SCHEMA}}, substituted at runtime.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# SQL layers, in dependency order.
SQL_FILES = [
    "01_tables_and_comments.sql",
    "02_dim_province.sql",
    "03_fraud_geo_views.sql",
    "04_metric_base.sql",
    "05_metric_view.sql",
    "06_geo_analysis_views.sql",
    "07_looker_views.sql",
]
VERIFY_FILE = "08_verify_all.sql"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def sql_dir() -> Path:
    for cand in (repo_root() / "sql", Path.cwd() / "sql", Path(__file__).resolve().parent / "sql"):
        if cand.is_dir():
            return cand
    raise FileNotFoundError("Could not locate the sql/ directory.")


def in_databricks() -> bool:
    """True when running on Databricks compute (job/notebook)."""
    return "DATABRICKS_RUNTIME_VERSION" in os.environ


def get_spark(profile: str | None):
    if in_databricks():
        from pyspark.sql import SparkSession
        s = SparkSession.getActiveSession()
        return s or SparkSession.builder.getOrCreate()
    # Local: Databricks Connect (serverless auto-negotiates the runtime).
    from databricks.connect import DatabricksSession
    builder = DatabricksSession.builder
    if profile:
        builder = builder.profile(profile)
    return builder.serverless().getOrCreate()


def get_workspace_client(profile: str | None):
    from databricks.sdk import WorkspaceClient
    if in_databricks() or not profile:
        return WorkspaceClient()
    return WorkspaceClient(profile=profile)


def split_statements(text: str) -> list[str]:
    """Split on top-level ';'. Statements wrapped in $$...$$ (metric-view YAML)
    are kept intact so their inner ';' / ':' are not split."""
    stmts, buf, in_dollar = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("--"):
            continue
        if "$$" in line:
            # toggle on each $$ occurrence
            in_dollar = (in_dollar != (line.count("$$") % 2 == 1))
        buf.append(line)
        if not in_dollar and line.rstrip().endswith(";"):
            chunk = "\n".join(buf).strip().rstrip(";").strip()
            if chunk:
                stmts.append(chunk)
            buf = []
    tail = "\n".join(buf).strip().rstrip(";").strip()
    if tail:
        stmts.append(tail)
    return stmts


def run_sql_file(w, warehouse_id: str, path: Path, catalog: str, schema: str,
                 show: bool = False) -> list | None:
    text = path.read_text().replace("{{CATALOG}}", catalog).replace("{{SCHEMA}}", schema)
    last_rows = None
    for i, stmt in enumerate(split_statements(text), 1):
        preview = " ".join(stmt.split())[:88]
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id, statement=stmt,
            catalog=catalog, schema=schema, wait_timeout="50s",
        )
        state = resp.status.state.value if resp.status and resp.status.state else "?"
        sid = resp.statement_id
        while state in ("PENDING", "RUNNING"):
            time.sleep(2)
            resp = w.statement_execution.get_statement(sid)
            state = resp.status.state.value
        if state != "SUCCEEDED":
            err = resp.status.error.message if resp.status and resp.status.error else "unknown"
            print(f"    [{i}] FAILED: {preview}\n         ERROR: {err}")
            sys.exit(1)
        nrows = len(resp.result.data_array) if resp.result and resp.result.data_array else None
        print(f"    [{i}] OK: {preview}" + (f"  ({nrows} rows)" if nrows is not None else ""))
        if resp.result and resp.result.data_array:
            cols = [c.name for c in resp.manifest.schema.columns]
            last_rows = (cols, resp.result.data_array)
            if show:
                print("       " + " | ".join(cols))
                for row in resp.result.data_array[:60]:
                    print("       " + " | ".join("" if v is None else str(v) for v in row))
    return last_rows


def write_tables(spark, catalog: str, schema: str) -> None:
    import generate_data
    tables = generate_data.generate()
    generate_data.summarize(tables)
    # The catalog must already exist (you supply your own). We only create the schema.
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")
    print(f"Writing tables to {catalog}.{schema} ...")
    for name, df in tables.items():
        sdf = spark.createDataFrame(df)
        (sdf.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
            .saveAsTable(f"`{catalog}`.`{schema}`.`{name}`"))
        print(f"  wrote {catalog}.{schema}.{name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Install the geo-fraud-lab into a UC schema.")
    ap.add_argument("--catalog", default=os.environ.get("GEO_FRAUD_CATALOG"))
    ap.add_argument("--schema", default=os.environ.get("GEO_FRAUD_SCHEMA", "geo_fraud_lab"))
    ap.add_argument("--warehouse-id", default=os.environ.get("GEO_FRAUD_WAREHOUSE_ID"))
    ap.add_argument("--profile", default=os.environ.get("DATABRICKS_PROFILE"))
    ap.add_argument("--skip-data", action="store_true", help="skip data generation (SQL only)")
    args = ap.parse_args()

    if not args.catalog:
        sys.exit("ERROR: --catalog / GEO_FRAUD_CATALOG is required.")
    if not args.warehouse_id:
        sys.exit("ERROR: --warehouse-id / GEO_FRAUD_WAREHOUSE_ID is required.")

    # Make scripts/ importable regardless of working directory.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    print("=" * 74)
    print(f"geo-fraud-lab install  ->  {args.catalog}.{args.schema}")
    print(f"  warehouse: {args.warehouse_id}   env: "
          f"{'databricks-job' if in_databricks() else 'local (Databricks Connect)'}")
    print("=" * 74)

    if not args.skip_data:
        spark = get_spark(args.profile)
        write_tables(spark, args.catalog, args.schema)

    w = get_workspace_client(args.profile)
    sd = sql_dir()
    for fname in SQL_FILES:
        print(f"\n>> {fname}")
        run_sql_file(w, args.warehouse_id, sd / fname, args.catalog, args.schema)

    print(f"\n>> {VERIFY_FILE}")
    run_sql_file(w, args.warehouse_id, sd / VERIFY_FILE, args.catalog, args.schema, show=True)

    print("\n" + "=" * 74)
    print(f"DONE. Lab installed into {args.catalog}.{args.schema}")
    print("=" * 74)


if __name__ == "__main__":
    main()
