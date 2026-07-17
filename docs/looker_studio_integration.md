# Looker Studio Integration Guide

This guide covers connecting Looker Studio to the `geo-fraud-lab` Databricks deployment and building a Tunaiku-style lending fraud dashboard from the `vw_ls_*` views.

---

## Important: No first-party connector

**There is no native/official Looker Studio ↔ Databricks connector.** Your options are:

### Option A — Third-party JDBC connector (e.g. CData)
- [CData Databricks connector for Looker Studio](https://www.cdata.com/drivers/databricks/looker-studio/) provides a Partner Connector that issues live SQL queries to a Databricks SQL warehouse.
- Requires a CData licence or trial.
- Best for: direct live query, no data movement.

### Option B — BigQuery bridge (native connector, no third-party licence)
- Replicate or federate the `vw_ls_*` views into BigQuery (e.g. via Databricks-to-BigQuery export or a Lakehouse Federation external table).
- Use Looker Studio's **native BigQuery connector** (free, no setup beyond GCP auth).
- Best for: teams already on Google Cloud / BigQuery.

### Option C — Direct SQL connector (Looker Studio community)
- Some community connectors support generic JDBC/ODBC. Search the [Looker Studio connector gallery](https://lookerstudio.google.com/data) for "Databricks."
- Maturity and support vary — validate before relying on it in production.

---

## Connection details

Fill these in when configuring your connector:

| Field | Value |
|---|---|
| **Host** | `<your-workspace>.cloud.databricks.com` |
| **HTTP Path** | `/sql/1.0/warehouses/<your-warehouse-id>` |
| **Catalog** | `<your_catalog>` |
| **Schema** | `geo_fraud_lab` (or your custom `--schema`) |
| **Port** | `443` |
| **Auth** | Personal Access Token (PAT) for demos; Service Principal OAuth for production |

### Auth recommendation
- **Demo/workshop**: PAT is simplest (generate in workspace **Settings → Developer → Access tokens**).
- **Production**: use a **Service Principal** with a client secret — not tied to a person, rotatable, cleaner Unity Catalog audit trail.

---

## Views and chart mapping

Each `vw_ls_*` view is purpose-built for a specific Looker Studio chart type:

| View | Recommended chart | Key fields |
|---|---|---|
| `vw_ls_portfolio_overview` | Scorecard / KPI tiles | `total_disbursed_idr`, `active_borrowers`, `npl_ratio`, `par30`, `approval_rate`, `fraud_rate`, `fraud_amount_idr` |
| `vw_ls_disbursement_by_month` | Time series / line chart | `disbursement_month`, `total_disbursed_idr`, `loans_funded`, `avg_loan_size_idr` |
| `vw_ls_portfolio_by_province` | Bubble map (lat/lon) | `province`, `latitude`, `longitude`, `latlong`, `total_disbursed_idr`, `npl_ratio` |
| `vw_ls_fraud_by_province` | Bar chart / map | `province`, `latitude`, `longitude`, `latlong`, `fraud_rate`, `fraud_amount_idr`, `applications` |
| `vw_ls_fraud_hotspots` | Bubble map (lat/lon) | `h3_cell`, `province`, `latitude`, `longitude`, `latlong`, `applications`, `fraud_rate` |
| `vw_ls_hotspots_kring` | Weighted bubble map | `h3_cell`, `latitude`, `longitude`, `latlong`, `applications`, `fraud_rate` |
| `vw_ls_distance_bands` | Bar chart | `distance_band`, `applications`, `fraud_applications`, `fraud_rate`, `avg_distance_km` |
| `vw_ls_fraud_rings` | Table | `device_id`, `num_customers`, `num_applications`, `fraud_applications`, `fraud_rate`, `bbox_span_km` |
| `vw_ls_impossible_travel` | Scatter chart | `implied_speed_kmh`, `distance_km`, `hours_between`, `home_province`, `application_province` |
| `vw_ls_fraud_by_month` | Time series / line chart | `application_month`, `applications`, `fraud_applications`, `fraud_rate`, `fraud_amount_idr` |

---

## Geo fields

### Bubble map (lat/lon separate fields)
For **Looker Studio bubble maps**, add `latitude` and `longitude` as separate fields and set their **semantic type** to `Latitude` and `Longitude` respectively in the data source settings.

### Combined latlong field
The `latlong` field contains a `"lat,lon"` string (e.g. `"-6.2146,106.8451"`). Some connectors accept this as a single **Geo** field — try it if your connector supports it; otherwise use the separate lat/lon fields.

---

## H3 hex maps (advanced)

Looker Studio's native chart types do **not** support H3 hexagon polygons. To render H3 hotspot density as a hex map:

1. Use a **Community Visualization** — e.g. a [deck.gl H3HexagonLayer](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer) hosted as a Looker Studio community viz.
2. Reference the `h3_cell` field from `vw_ls_fraud_hotspots` (resolution 7 cells) as the hex identifier.
3. Use `fraud_rate` or `applications` as the weight/color field.

See the [Looker Studio Community Visualizations docs](https://developers.google.com/looker-studio/visualization) for how to build and deploy a custom viz.

---

## Sharing reports without report-as-code

Looker Studio has **no report import/export as code** — you cannot version-control the report definition itself and import it via a file. The supported sharing pattern is:

1. **Create a template report** connected to your `geo_fraud_lab` deployment.
2. **Share the template link** (`File → Share → Get report link → Anyone with the link`).
3. Participants click the link and choose **"Make a copy"**.
4. On copy, they swap the data source to their own `geo_fraud_lab` deployment.
5. Because field names in `vw_ls_*` are **stable and identical** across all deployments of this repo, the copied report works immediately after the data source swap.

> **Tip**: document the template link in your workshop notes. You — the workshop facilitator — create the template once against your own deployment; participants copy it and swap the source.

---

## Looker (enterprise) note

If you or your customer also use **Looker (enterprise)** with LookML:

- The connection mechanism is the same (SQL warehouse host + HTTP path), but Looker has a **native Databricks dialect** — no third-party connector needed.
- The semantic layer (measures, dimensions) lives in **LookML** rather than in the `vw_ls_*` views.
- The `vw_ls_*` views can still serve as underlying base views in LookML, or you can map the measures directly to `metrics_lending` (Unity Catalog Metric View) as the governed source of truth.
- Looker enterprise also supports **PDTs** (persistent derived tables) — you'll need to grant `CREATE TABLE` on a scratch schema.
