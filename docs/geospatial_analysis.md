# Geospatial Analysis Guide

This guide explains how each fraud-signal view is computed, the SQL patterns used, and notes on Databricks H3 and spatial function requirements.

---

## Warehouse requirement

> ⚠️ **H3 and ST_ spatial functions require a Photon-enabled or serverless SQL warehouse.**  
> Standard non-Photon warehouses will error on H3 steps (`h3_longlatash3string`, `h3_tochildren`, etc.).  
> Serverless SQL warehouses are Photon-enabled by default.

---

## Fraud signals overview

| Signal | Description | View |
|---|---|---|
| **Impossible travel** | Two applications from the same customer at locations far apart in a short time — implies an impossible physical journey | `vw_fraud_signals` |
| **Location mismatch** | Application lat/lon is far (>50 km) from the customer's registered home province centroid | `vw_fraud_signals` |
| **Device ring** | Same `device_id` used by many distinct customers — suggests a shared/spoofed device | `vw_fraud_signals` |
| **Foreign IP** | `ip_country != 'ID'` — application submitted from outside Indonesia | `vw_fraud_signals` |
| **H3 hotspot** | H3 cells with disproportionately high fraud concentration | `vw_fraud_hotspots` |

---

## `vw_fraud_signals` — how it works

### Impossible travel
Uses `ST_DistanceSphere` (Haversine distance in metres) combined with a `LAG` window to get the previous application's location and timestamp for the same customer:

```sql
WITH consecutive AS (
  SELECT
    application_id,
    customer_id,
    app_lat, app_lon,
    application_ts,
    LAG(app_lat)  OVER (PARTITION BY customer_id ORDER BY application_ts) AS prev_lat,
    LAG(app_lon)  OVER (PARTITION BY customer_id ORDER BY application_ts) AS prev_lon,
    LAG(application_ts) OVER (PARTITION BY customer_id ORDER BY application_ts) AS prev_ts
  FROM fact_loan_application
)
SELECT
  *,
  ST_DistanceSphere(
    POINT(app_lon, app_lat),
    POINT(prev_lon, prev_lat)
  ) / 1000.0 AS distance_km,
  (unix_timestamp(application_ts) - unix_timestamp(prev_ts)) / 3600.0 AS time_gap_hours,
  (ST_DistanceSphere(...) / 1000.0) /
    NULLIF((unix_timestamp(application_ts) - unix_timestamp(prev_ts)) / 3600.0, 0)
    AS implied_speed_kmh
FROM consecutive
WHERE prev_lat IS NOT NULL
```

Applications with `implied_speed_kmh > 900` (faster than a commercial jet over water) are flagged as impossible travel. The workshop dataset produces outliers at ~2,000–2,900 km/h.

### Location mismatch
Each customer has a registered `home_lat` / `home_lon`. The distance from their application location to their home is computed via `ST_DistanceSphere`. Applications where this distance exceeds a threshold are flagged.

> **Note on fraud rates**: distance is a *strong-but-probabilistic* signal. Fraud probability rises sharply with distance (legitimate long-distance loans exist — travel, out-of-province work). The dataset reflects this: fraud rate is ~65–78% for applications >50 km from home, not a hard 100%.

### Device rings
A window aggregation counts distinct `customer_id` per `device_id`. Devices shared across many customers (threshold: configurable in the view) indicate a device ring.

```sql
SELECT
  device_id,
  COUNT(DISTINCT customer_id) AS customer_count,
  COUNT(*) FILTER (WHERE is_fraud) AS fraud_count
FROM fact_loan_application
GROUP BY device_id
HAVING COUNT(DISTINCT customer_id) > 5
```

---

## `vw_fraud_hotspots` — H3 aggregation

H3 cells are pre-computed in `fact_loan_application` at resolution 7 (cells ~1.2 km across) using:

```sql
h3_longlatash3string(app_lon, app_lat, 7) AS h3_cell_r7
```

The hotspot view aggregates to the cell level and computes a centroid lat/lon for mapping:

```sql
SELECT
  h3_cell_r7,
  h3_togeoboundary(h3_cell_r7)  AS cell_polygon,   -- WKT, for rendering
  AVG(app_lat)  AS centroid_lat,
  AVG(app_lon)  AS centroid_lon,
  COUNT(*)      AS app_count,
  SUM(is_fraud) AS fraud_count,
  AVG(is_fraud) AS fraud_rate
FROM fact_loan_application
GROUP BY h3_cell_r7
ORDER BY fraud_rate DESC
```

The centroid is used in Looker Studio bubble maps (since Looker Studio can't render H3 polygons natively — see the Looker Studio integration guide for the Community Visualization approach).

---

## `vw_geo_distance_bands` — distance-band analysis

Groups applications into three bands based on distance from home:

| Band | Distance | Expected fraud rate |
|---|---|---|
| `<=10km` | ≤ 10 km from home province centroid | ~1–2% |
| `10-50km` | 10–50 km | ~2–5% |
| `>50km` | > 50 km | ~65–78% (probabilistic) |

```sql
SELECT
  CASE
    WHEN distance_km <= 10  THEN '<=10km'
    WHEN distance_km <= 50  THEN '10-50km'
    ELSE '>50km'
  END AS distance_band,
  COUNT(*)      AS total_apps,
  SUM(is_fraud) AS fraud_count,
  AVG(is_fraud) AS fraud_rate
FROM (
  SELECT
    is_fraud,
    ST_DistanceSphere(POINT(app_lon, app_lat), POINT(home_lon, home_lat)) / 1000.0 AS distance_km
  FROM fact_loan_application fa
  JOIN dim_customer dc ON fa.customer_id = dc.customer_id
) sub
GROUP BY distance_band
```

The ">50km → ~65–78% fraud" pattern is the key insight for a lending fraud model: **location mismatch is a strong prior**, but not a hard rule. Legitimate long-distance applications (students, migrant workers) exist and must not be automatically rejected.

---

## H3 resolution guide

| Resolution | Approx. cell size | Use case |
|---|---|---|
| 5 | ~252 km² (~9 km across) | Country/regional heatmap |
| 6 | ~36 km² | City-level density |
| **7** | **~5 km²** | **Used in this lab — neighbourhood-level** |
| 8 | ~0.7 km² | Street-level (high row count) |

Resolution 7 balances granularity (neighbourhood) with manageable cardinality (~10k–50k cells for Indonesia).

---

## Useful Databricks spatial functions

| Function | Description |
|---|---|
| `h3_longlatash3string(lon, lat, resolution)` | Compute H3 cell index from coordinates |
| `h3_togeoboundary(h3_cell)` | WKT polygon of the H3 cell boundary |
| `h3_tochildren(h3_cell, child_resolution)` | Child cells at a finer resolution |
| `h3_distance(cell_a, cell_b)` | Grid distance between two H3 cells |
| `ST_DistanceSphere(point_a, point_b)` | Haversine distance in metres |
| `ST_Within(point, polygon)` | Point-in-polygon test |
| `ST_Intersects(geom_a, geom_b)` | Geometry intersection test |
| `POINT(lon, lat)` | Construct a point geometry |

All require a **Photon-enabled or serverless SQL warehouse**.
