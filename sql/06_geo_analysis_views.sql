-- geo-fraud-lab :: 06 — EXPANDED geospatial analysis views (vw_geo_*).
-- These go beyond the per-application signals: H3 k-ring neighborhood density,
-- province choropleth aggregates, home-vs-application distance-band distributions,
-- and device-ring spatial clustering with a representative centroid.
-- All are shaped BI-ready: separate latitude/longitude columns AND a combined
-- "lat,lon" latlong field for map charts. Requires Databricks H3 + ST_ functions.

-- =====================================================================
-- vw_geo_hotspots_kring : H3 res-7 hotspot density using k-ring (k=1) NEIGHBORHOOD
-- aggregation. For each cell we sum applications/fraud across the cell AND its
-- immediate hex neighbors (h3_kring(cell, 1)), giving a smoothed local density
-- that reveals fraud clusters spanning adjacent cells. Centroid lat/lon of the
-- center cell drives a weighted bubble map.
-- =====================================================================
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_geo_hotspots_kring
COMMENT 'H3 res-7 hotspots with k-ring (k=1) neighborhood density for weighted bubble maps.' AS
WITH cell_stats AS (
  SELECT h3_res7,
         COUNT(*)                                  AS cell_applications,
         SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS cell_fraud
  FROM {{CATALOG}}.{{SCHEMA}}.fact_loan_application
  GROUP BY h3_res7
),
cell_ring AS (  -- expand each cell into itself + its 6 neighbors
  SELECT h3_res7 AS center_cell, EXPLODE(h3_kring(h3_res7, 1)) AS neighbor_cell
  FROM cell_stats
)
SELECT
  cr.center_cell                                                                              AS h3_cell,
  ROUND(CAST(get_json_object(h3_centerasgeojson(cr.center_cell), '$.coordinates[1]') AS DOUBLE), 6) AS latitude,
  ROUND(CAST(get_json_object(h3_centerasgeojson(cr.center_cell), '$.coordinates[0]') AS DOUBLE), 6) AS longitude,
  CONCAT(
    ROUND(CAST(get_json_object(h3_centerasgeojson(cr.center_cell), '$.coordinates[1]') AS DOUBLE), 6), ',',
    ROUND(CAST(get_json_object(h3_centerasgeojson(cr.center_cell), '$.coordinates[0]') AS DOUBLE), 6)
  )                                                                                           AS latlong,
  MAX(cs_c.cell_applications)                                        AS cell_applications,
  MAX(cs_c.cell_fraud)                                              AS cell_fraud,
  COUNT(cs_n.h3_res7)                                              AS active_neighbor_cells,
  SUM(COALESCE(cs_n.cell_applications, 0))                          AS kring_applications,
  SUM(COALESCE(cs_n.cell_fraud, 0))                                AS kring_fraud,
  ROUND(SUM(COALESCE(cs_n.cell_fraud, 0)) / NULLIF(SUM(COALESCE(cs_n.cell_applications, 0)), 0), 4)
                                                                    AS kring_fraud_rate
FROM cell_ring cr
JOIN cell_stats cs_c ON cr.center_cell = cs_c.h3_res7
LEFT JOIN cell_stats cs_n ON cr.neighbor_cell = cs_n.h3_res7
GROUP BY cr.center_cell
HAVING SUM(COALESCE(cs_n.cell_fraud, 0)) > 0
ORDER BY kring_fraud DESC;

-- =====================================================================
-- vw_geo_province_choropleth : single-grain (borrower home province) aggregates
-- for a filled/region map — fraud_rate, disbursed, outstanding, PAR90 per province,
-- with province name (standard geocoding) + centroid lat/lon + latlong.
-- =====================================================================
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_geo_province_choropleth
COMMENT 'Province-grain choropleth aggregates (fraud_rate, disbursed, PAR90) with centroid coords.' AS
SELECT
  b.province,
  dp.center_lat                              AS latitude,
  dp.center_lon                              AS longitude,
  CONCAT(dp.center_lat, ',', dp.center_lon)  AS latlong,
  COUNT(*)                                   AS applications,
  SUM(CASE WHEN b.is_fraud THEN 1 ELSE 0 END) AS fraud_applications,
  ROUND(AVG(CASE WHEN b.is_fraud THEN 1.0 ELSE 0.0 END), 4) AS fraud_rate,
  COUNT(b.loan_id)                           AS loans_funded,
  SUM(b.principal_amount)                    AS total_disbursed_idr,
  SUM(b.outstanding_principal)               AS outstanding_principal_idr,
  ROUND(SUM(CASE WHEN b.dpd >= 90 THEN b.outstanding_principal ELSE 0 END)
        / NULLIF(SUM(b.outstanding_principal), 0), 4) AS par90
FROM {{CATALOG}}.{{SCHEMA}}.vw_metric_base b
JOIN {{CATALOG}}.{{SCHEMA}}.dim_province dp ON b.province = dp.province
GROUP BY b.province, dp.center_lat, dp.center_lon
ORDER BY fraud_rate DESC;

-- =====================================================================
-- vw_geo_distance_bands : distribution of applications across bands of the
-- home-vs-application distance (ST_DistanceSphere). Fraud rate climbs sharply
-- with distance — the core "location mismatch" geospatial signal.
-- =====================================================================
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_geo_distance_bands
COMMENT 'Home-vs-application distance-band distribution with fraud rate per band.' AS
SELECT
  band_order,
  distance_band,
  COUNT(*)                                                 AS applications,
  SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)                AS fraud_applications,
  ROUND(AVG(CASE WHEN is_fraud THEN 1.0 ELSE 0.0 END), 4)  AS fraud_rate,
  ROUND(AVG(home_distance_km), 2)                          AS avg_distance_km,
  ROUND(MAX(home_distance_km), 2)                          AS max_distance_km
FROM (
  SELECT
    is_fraud, home_distance_km,
    CASE
      WHEN home_distance_km <  10  THEN 1
      WHEN home_distance_km <  50  THEN 2
      WHEN home_distance_km < 150  THEN 3
      WHEN home_distance_km < 500  THEN 4
      ELSE 5 END AS band_order,
    CASE
      WHEN home_distance_km <  10  THEN '0-10 km'
      WHEN home_distance_km <  50  THEN '10-50 km'
      WHEN home_distance_km < 150  THEN '50-150 km'
      WHEN home_distance_km < 500  THEN '150-500 km'
      ELSE '500+ km' END AS distance_band
  FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_signals
)
GROUP BY band_order, distance_band
ORDER BY band_order;

-- =====================================================================
-- vw_geo_device_ring_clusters : device rings (one device across >=5 customers)
-- summarized as a spatial cluster — representative centroid (mean lat/lon of the
-- ring's applications), bounding-box diagonal span (km) showing how geographically
-- dispersed the ring is, and the number of distinct origin provinces touched.
-- =====================================================================
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_geo_device_ring_clusters
COMMENT 'Device-ring spatial clusters: representative centroid, bounding-box span (km), provinces touched.' AS
WITH ring AS (
  SELECT
    s.device_id,
    COUNT(*)                                     AS num_applications,
    COUNT(DISTINCT s.customer_id)                AS num_customers,
    SUM(CASE WHEN s.is_fraud THEN 1 ELSE 0 END)  AS fraud_applications,
    COUNT(DISTINCT s.app_province)               AS provinces_touched,
    ROUND(AVG(s.app_lat), 6)                     AS latitude,
    ROUND(AVG(s.app_lon), 6)                     AS longitude,
    MIN(s.app_lat) AS min_lat, MAX(s.app_lat) AS max_lat,
    MIN(s.app_lon) AS min_lon, MAX(s.app_lon) AS max_lon,
    SUM(s.requested_amount)                      AS total_requested_idr
  FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_signals s
  GROUP BY s.device_id
  HAVING COUNT(DISTINCT s.customer_id) >= 5
)
SELECT
  device_id,
  num_applications,
  num_customers,
  fraud_applications,
  ROUND(fraud_applications / NULLIF(num_applications, 0), 4) AS fraud_rate,
  provinces_touched,
  latitude,
  longitude,
  CONCAT(latitude, ',', longitude)              AS latlong,
  ROUND(ST_DistanceSphere(ST_Point(min_lon, min_lat), ST_Point(max_lon, max_lat)) / 1000.0, 2)
                                                AS bbox_span_km,
  total_requested_idr
FROM ring
ORDER BY num_customers DESC, bbox_span_km DESC;
