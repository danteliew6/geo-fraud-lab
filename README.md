# geo-fraud-lab

A self-contained, parameterized Databricks lab: a digital-lending geospatial fraud dataset with a governed star schema, H3 spatial analytics, fraud-signal detection views, and a Looker Studio integration pack. Drop into **any Unity Catalog workspace** in one command.

---

## What you get

| Object | Description |
|---|---|
| **Gold star schema** | `dim_customer`, `dim_province`, `fact_loan_application` (with lat/lon, H3, device_id, fraud signals), `fact_loan`, `fact_repayment` — ~20k customers, ~30k applications, ~18k loans, ~190k repayments |
| **Fraud-signal views** | `vw_fraud_signals` — impossible travel (ST_DistanceSphere + LAG), location mismatch, device rings, foreign IP flags |
| **H3 hotspot view** | `vw_fraud_hotspots` — H3 cell aggregation with centroid lat/lon for mapping |
| **Geospatial analysis** | `vw_geo_hotspots_kring`, `vw_geo_province_choropleth`, `vw_geo_distance_bands`, `vw_geo_device_ring_clusters` — k-ring density, choropleth aggregates, distance-band fraud rates, device-ring clusters |
| **Metric View** | `metrics_lending` — governed measures: disbursed, active borrowers, NPL ratio, PAR30, approval rate, fraud rate, fraud amount — all by province/month/credit band |
| **10 Looker Studio views** | `vw_ls_portfolio_overview`, `vw_ls_disbursement_by_month`, `vw_ls_portfolio_by_province`, `vw_ls_fraud_by_province`, `vw_ls_fraud_hotspots`, `vw_ls_hotspots_kring`, `vw_ls_distance_bands`, `vw_ls_fraud_rings`, `vw_ls_impossible_travel`, `vw_ls_fraud_by_month` — lat/lon + `latlong` combined field ready for BI maps |
| ✅ **AI/BI Fraud Dashboard** | **Geo Fraud Command Center** — auto-deployed by `bundle deploy`. Geospatial hotspot map, fraud KPIs, province breakdown, impossible-travel table, month-by-month trend. |

Fraud is driven by **geospatial signals only**: impossible travel, location mismatch, device rings, foreign IP, and H3 hotspot concentration — realistic and probabilistic (not perfectly labelled).

---

## Quickstart

Deployment is a Declarative Asset Bundle (DAB). Everything runs on serverless and
is fully self-contained — no SQL warehouse routing, no manual template rendering.
Designed to clone-and-run on a **Databricks Free Edition** workspace.

**Requirements:** [Databricks CLI](https://docs.databricks.com/dev-tools/cli/index.html) **v0.281.0+** (native dashboard `dataset_catalog`/`dataset_schema`), installed and authenticated.

```bash
git clone https://github.com/danteliew6/geo-fraud-lab
cd geo-fraud-lab

# 1 — deploy the job + both dashboards to your workspace
databricks bundle deploy

# 2 — run the install job (generates data + builds all SQL layers on serverless)
databricks bundle run install_geo_fraud_lab
```

On **Free Edition** the defaults just work: `catalog=workspace`, `schema=geo_fraud_lab`,
and `warehouse_id` is resolved by looking up the built-in **Serverless Starter Warehouse**.
On other workspaces, override with vars:

```bash
databricks bundle deploy \
  --var="catalog=my_catalog" \
  --var="schema=geo_fraud_lab" \
  --var="warehouse_id=YOUR_WAREHOUSE_ID"
databricks bundle run install_geo_fraud_lab \
  --var="catalog=my_catalog" --var="schema=geo_fraud_lab"
```

The install job runs two serverless tasks in sequence:
1. **generate_data** — generates ~20k customers / ~30k applications / ~18k loans / ~200k repayments and writes base tables to Unity Catalog
2. **run_sql** — reads the bundled SQL files from the workspace and executes all layers (H3 index, fraud/geo views, metric view, Looker views) via serverless Spark — no SQL warehouse required

`bundle deploy` also deploys two AI/BI dashboards. Their dataset queries are
schema-qualified (`geo_fraud_lab.<table>`) and DAB supplies the leading catalog via
`dataset_catalog`, so they resolve as `<catalog>.geo_fraud_lab.<table>`:
- **Geo Fraud Command Center** — geospatial fraud analysis (hotspot map, impossible-travel, device rings, distance bands, trend)
- **Tunaiku Lending 360** — portfolio overview (disbursed, NPL, PAR30, approval rate by province)

---

## Prerequisites

- Databricks workspace with **Unity Catalog** enabled (**Free Edition** works out of the box)
- **Serverless** compute — required for `ST_*` geospatial functions, `H3`, and Metric Views (or a **DBR 17.3+ LTS** cluster)
- The schema is auto-created; the catalog (`workspace` on Free Edition) must already exist

---

## Configuration

All parameters are DAB variables — pass with `--var="name=value"` on `bundle deploy` / `bundle run`:

| Variable | Default | Description |
|---|---|---|
| `catalog` | `workspace` | Unity Catalog catalog to install into. Must already exist (`workspace` on Free Edition). |
| `schema` | `geo_fraud_lab` | Schema to create. Created automatically by the install job. |
| `warehouse_id` | _lookup: "Serverless Starter Warehouse"_ | SQL warehouse that backs the dashboards. Auto-resolved on Free Edition; override with `--var="warehouse_id=..."` elsewhere. |

The install job itself needs **no** warehouse — it runs on serverless Spark. `warehouse_id` is only used to back the two AI/BI dashboards.

### Finding your warehouse ID

In your Databricks workspace: **Settings → SQL Warehouses** → click your warehouse → **Connection details** → copy the value after `/sql/1.0/warehouses/`.

---

## Looker Studio integration

See [`docs/looker_studio_integration.md`](docs/looker_studio_integration.md) for the full guide, including:
- Connection setup (host, HTTP path, auth)
- Which `vw_ls_*` view maps to which chart type
- The `latlong` combined field for geo charts
- H3 hex maps via Community Visualization (deck.gl)
- Template-copy pattern for sharing reports without report-as-code

---

## Geospatial analysis

See [`docs/geospatial_analysis.md`](docs/geospatial_analysis.md) for:
- How each fraud signal is computed (SQL patterns + H3 functions)
- Interpreting the distance-band chart
- Notes on H3 warehouse requirements

---

## Uninstall

Run [`sql/99_uninstall.sql`](sql/99_uninstall.sql) in the Databricks SQL editor after replacing `{{CATALOG}}` and `{{SCHEMA}}` with your values. To tear down the DAB-deployed job and dashboards, run `databricks bundle destroy`.

---

## Repo structure

```
geo-fraud-lab/
├── README.md
├── .gitignore
├── databricks.yml              # DAB root config
├── resources/
│   ├── install_job.yml         # DAB job definition (2-task serverless install pipeline)
│   └── dashboard.yml           # DAB dashboard resources (native dataset_catalog/schema)
├── dashboards/
│   ├── geo_fraud.lvdash.json      # AI/BI Geo Fraud Command Center (auto-deployed)
│   └── tunaiku_c360.lvdash.json   # AI/BI Tunaiku Lending 360 (auto-deployed)
├── notebooks/
│   ├── 01_generate_data.py     # DAB task: generate + write base tables (serverless)
│   └── 02_run_sql.py           # DAB task: execute bundled SQL layers on serverless
├── scripts/
│   └── generate_data.py        # Deterministic synthetic data generator (no Databricks dependency)
├── sql/
│   ├── 01_tables_and_comments.sql   # H3 index + table/column comments
│   ├── 02_dim_province.sql          # Province dimension with lat/lon centroids
│   ├── 03_fraud_geo_views.sql       # vw_fraud_signals, vw_fraud_hotspots
│   ├── 04_metric_base.sql           # Base aggregation for metric view
│   ├── 05_metric_view.sql           # Unity Catalog Metric View (metrics_lending)
│   ├── 06_geo_analysis_views.sql    # vw_geo_* geospatial analysis views
│   ├── 07_looker_views.sql          # 10 vw_ls_* views for Looker Studio
│   ├── 08_verify_all.sql            # Row-count + metric verification
│   └── 99_uninstall.sql             # Teardown
└── docs/
    ├── looker_studio_integration.md # Looker Studio connection guide
    └── geospatial_analysis.md       # Fraud signal SQL patterns + H3 notes
```

---

## Known issues / notes

- **Distance-band fraud rate**: fraud probability rises sharply with distance from home province but is **probabilistic** (~65–78% above 50 km), not a hard rule — legitimate long-distance loans exist.
- **ST_ / H3 functions** (`ST_DistanceSphere`, `h3_longlatash3string`) and **Metric Views** require a **Serverless cluster** or **DBR 17.3+ LTS**. Older runtimes will error on the geo/metric view steps.

---

## License

MIT
