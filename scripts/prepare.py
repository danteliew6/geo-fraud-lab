#!/usr/bin/env python3
"""
Render dashboard JSON templates before `databricks bundle deploy`.

Substitutes {{CATALOG}}, {{SCHEMA}}, {{WAREHOUSE_ID}} tokens in the
dashboard source files and writes the results to dashboards/rendered/.
DAB is then pointed at the rendered files, which contain real values.

Usage:
    python scripts/prepare.py --catalog main --schema geo_fraud_lab
    python scripts/prepare.py --catalog main --schema geo_fraud_lab --warehouse-id abc123
"""
import argparse, json, os, pathlib, re, sys

REPO_ROOT   = pathlib.Path(__file__).parent.parent
DASH_SRC    = REPO_ROOT / "dashboards"
DASH_OUT    = REPO_ROOT / "dashboards" / "rendered"
TEMPLATES   = ["geo_fraud_dashboard.json", "tunaiku_c360_dashboard.json"]

def render(catalog: str, schema: str, warehouse_id: str) -> None:
    DASH_OUT.mkdir(parents=True, exist_ok=True)
    for name in TEMPLATES:
        src = DASH_SRC / name
        if not src.exists():
            print(f"  SKIP {name} (not found)")
            continue
        text = src.read_text()
        text = text.replace("{{CATALOG}}",      catalog)
        text = text.replace("{{SCHEMA}}",       schema)
        text = text.replace("{{WAREHOUSE_ID}}", warehouse_id)
        remaining = set(re.findall(r"\{\{[A-Z_]+\}\}", text))
        if remaining:
            print(f"  WARNING {name}: unsubstituted tokens {remaining}", file=sys.stderr)
        out = DASH_OUT / name
        out.write_text(text)
        print(f"  ✅ rendered {name} → dashboards/rendered/{name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render dashboard JSON templates for DAB deploy")
    parser.add_argument("--catalog",      default="main",          help="Unity Catalog catalog name")
    parser.add_argument("--schema",       default="geo_fraud_lab", help="Schema name")
    parser.add_argument("--warehouse-id", default="",              help="SQL warehouse ID (optional)")
    args = parser.parse_args()
    print(f"Rendering dashboards: catalog={args.catalog}, schema={args.schema}")
    render(args.catalog, args.schema, args.warehouse_id)
    print("Done — run 'databricks bundle deploy' next.")
