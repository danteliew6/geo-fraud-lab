# geo-fraud-lab

A self-contained, parameterized Databricks lab: a digital-lending geospatial fraud dataset with a governed star schema, H3 spatial analytics, fraud-signal detection views, and a Looker Studio integration pack. Drop into **any Unity Catalog workspace** in one command.

---

## What you get

| Object | Description |
|---|---|
| **Gold star schema** | `dim_customer`, `dim_province`, `fact_loan_application` (with lat/lon, H3, device_id, fraud signals), `fact_loan`, `fact_repayment` — ~20k customers, ~30k applications, ~18k loans, ~190k repayments |
| **Fraud-signal views** | `vw_fraud_signals` — impossible travel (ST_DistanceSphere + LAG), location mismatch, device rings, foreign IP flags |
| **H3 hotspot view** | `vw_fraud_hotspots` — H3 cell aggregation with centroid lat/lon for mapping |
| **Geospatial analysis** | `vw_geo_analysis`, `vw_distance_bands` — distance-band fraud rates, province aggregates |
| **Metric View** | `metrics_lending` — governed measures: disbursed, active borrowers, NPL ratio, PAR30, approval rate, fraud rate, fraud amount — all by province/month/credit band |
| **8 Looker Studio views** | `vw_ls_portfolio`, `vw_ls_fraud_map`, `vw_ls_impossible_travel`, `vw_ls_fraud_rings`, `vw_ls_province_fraud`, `vw_ls_trend`, `vw_ls_geo_analysis`, `vw_ls_distance_bands` — lat/lon + `latlong` combined field ready for BI maps |
| ✅ **AI/BI Fraud Dashboard** | **Geo Fraud Command Center** — auto-deployed by Run All; link printed at the end. Geospatial hotspot map, fraud KPIs, province breakdown, impossible-travel table, month-by-month trend. |

Fraud is driven by **geospatial signals only**: impossible travel, location mismatch, device rings, foreign IP, and H3 hotspot concentration — realistic and probabilistic (not perfectly labelled).

---

## Quickstart — No CLI needed

1. Open your Databricks workspace
2. Go to **Workspace → Import**
3. Paste this URL and click Import:
   ```
   https://raw.githubusercontent.com/danteliew6/geo-fraud-lab/main/notebooks/install_lab.py
   ```
4. Open the imported notebook
4a. Attach a **Serverless** or **DBR 17.3+** cluster
5. Fill in the widgets: **catalog** (must exist), **schema** (default: `geo_fraud_lab`), and optionally **warehouse HTTP path** (for Looker Studio — not needed for installation)
6. Click **Run All**

The notebook downloads the data files from GitHub, generates the dataset, builds all tables and views, and prints a verification summary.

> **Finding your warehouse HTTP path:** In your workspace, go to **Settings → SQL Warehouses** → click your warehouse → **Connection details** → copy the **HTTP path** value (e.g. `/sql/1.0/warehouses/abc123`). You will need this to connect Looker Studio after installation.

---

## Prerequisites

- Databricks workspace with **Unity Catalog** enabled
- An existing **catalog** you can create schemas in (the schema is created for you)
- A **Serverless cluster** or **DBR 17.3+ LTS cluster** — required for ST_ geospatial functions and Metric Views

---

## Advanced: CLI install

If you prefer running from a local terminal:

```bash
git clone https://github.com/danteliew6/geo-fraud-lab
cd geo-fraud-lab

uv run --with 'databricks-connect==15.*,databricks-sdk,pandas,numpy,pyarrow' \
  python scripts/run_lab.py \
  --profile       YOUR_CLI_PROFILE \
  --catalog       YOUR_CATALOG \
  --schema        geo_fraud_lab \
  --warehouse-id  YOUR_WAREHOUSE_ID
```

Requires Python 3.9+, [uv](https://docs.astral.sh/uv/), and the [Databricks CLI](https://docs.databricks.com/dev-tools/cli/index.html) configured (`databricks configure --profile <name>`).

The installer will:
1. Generate a seeded, deterministic synthetic dataset (same data every run)
2. Write the gold star-schema tables to `<catalog>.<schema>` via Databricks Connect
3. Execute the SQL layers in order (tables → geo/fraud views → metric view → Looker Studio views)
4. Verify every object and print a row-count + metric report

Total run time: ~3–5 minutes on a serverless warehouse.

---

## Configuration

All parameters can be passed as CLI flags or environment variables:

| CLI flag | Environment variable | Default | Description |
|---|---|---|---|
| `--profile` | `DATABRICKS_PROFILE` | _(required locally)_ | Databricks CLI profile name. Omit inside a Databricks job (uses ambient credentials). |
| `--catalog` | `GEO_FRAUD_CATALOG` | _(required)_ | Unity Catalog catalog to install into. Must already exist. |
| `--schema` | `GEO_FRAUD_SCHEMA` | `geo_fraud_lab` | Schema to create. Created automatically. |
| `--warehouse-id` | `GEO_FRAUD_WAREHOUSE_ID` | _(required)_ | SQL warehouse ID. Find it in **Settings → SQL Warehouses → Connection details**. |
| `--skip-data` | — | false | Skip data generation; re-run the SQL layers only (fast re-deploy). |

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

Run [`sql/99_uninstall.sql`](sql/99_uninstall.sql) in the Databricks SQL editor after replacing `{{CATALOG}}` and `{{SCHEMA}}` with your values, or pass `--uninstall` to the installer (if supported by your version).

---

## Repo structure

```
geo-fraud-lab/
├── README.md
├── .gitignore
├── dashboards/
│   └── geo_fraud_dashboard.json   # Parameterized AI/BI dashboard (auto-deployed by notebook)
├── notebooks/
│   └── install_lab.py      # One-click Databricks notebook installer (import URL → Run All)
├── scripts/
│   ├── run_lab.py          # End-to-end installer (parameterized)
│   └── generate_data.py    # Deterministic synthetic data generator (no Databricks dependency)
├── sql/
│   ├── 01_tables_and_comments.sql   # H3 index + table/column comments
│   ├── 02_dim_province.sql          # Province dimension with lat/lon centroids
│   ├── 03_fraud_geo_views.sql       # vw_fraud_signals, vw_fraud_hotspots
│   ├── 04_metric_base.sql           # Base aggregation for metric view
│   ├── 05_metric_view.sql           # Unity Catalog Metric View (metrics_lending)
│   ├── 06_geo_analysis_views.sql    # vw_geo_analysis, vw_distance_bands
│   ├── 07_looker_views.sql          # 8 vw_ls_* views for Looker Studio
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
