-- geo-fraud-lab :: 07 — LOOKER STUDIO INTEGRATION PACK — curated BI-friendly views.
-- BI tools connect to these as regular Databricks views (business-friendly column
-- names, plain SQL; they cannot call MEASURE()). Map views expose latitude,
-- longitude AND a combined "latlong" string (a Google Maps geo field in Looker
-- Studio uses a single "lat,lon" field).

-- 1) Portfolio KPI snapshot (single row) -> Scorecard tiles
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_portfolio_overview
COMMENT 'Looker Studio: single-row portfolio KPI snapshot for scorecards.' AS
SELECT
  SUM(principal_amount)                                                                       AS total_disbursed_idr,
  COUNT(loan_id)                                                                              AS loans_funded,
  COUNT(DISTINCT CASE WHEN loan_status IN ('current','delinquent') THEN customer_id END)      AS active_borrowers,
  ROUND(AVG(principal_amount))                                                                AS avg_loan_size_idr,
  SUM(outstanding_principal)                                                                  AS outstanding_principal_idr,
  ROUND(SUM(CASE WHEN dpd >= 90 THEN outstanding_principal ELSE 0 END)/NULLIF(SUM(outstanding_principal),0),4) AS npl_ratio,
  ROUND(SUM(CASE WHEN dpd >  30 THEN outstanding_principal ELSE 0 END)/NULLIF(SUM(outstanding_principal),0),4) AS par30,
  ROUND(SUM(CASE WHEN dpd >= 90 THEN outstanding_principal ELSE 0 END)/NULLIF(SUM(outstanding_principal),0),4) AS par90,
  ROUND(AVG(CASE WHEN decision = 'approved' THEN 1.0 ELSE 0.0 END),4)                         AS approval_rate,
  ROUND(SUM(repay_paid)/NULLIF(SUM(repay_due),0),4)                                           AS collection_rate,
  ROUND(AVG(interest_rate_pa),4)                                                              AS avg_interest_rate_pa,
  ROUND(AVG(CASE WHEN is_fraud THEN 1.0 ELSE 0.0 END),4)                                      AS fraud_rate,
  SUM(CASE WHEN is_fraud THEN requested_amount ELSE 0 END)                                    AS fraud_amount_idr,
  SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)                                                   AS flagged_applications
FROM {{CATALOG}}.{{SCHEMA}}.vw_metric_base;

-- 2) Disbursement trend by month -> Time-series line/bar
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_disbursement_by_month
COMMENT 'Looker Studio: monthly disbursement trend.' AS
SELECT
  DATE_TRUNC('MONTH', disbursement_date)  AS disbursement_month,
  SUM(principal_amount)                   AS total_disbursed_idr,
  COUNT(*)                                AS loans_funded,
  ROUND(AVG(principal_amount))            AS avg_loan_size_idr,
  SUM(outstanding_principal)              AS outstanding_principal_idr
FROM {{CATALOG}}.{{SCHEMA}}.fact_loan
GROUP BY DATE_TRUNC('MONTH', disbursement_date)
ORDER BY disbursement_month;

-- 3) Portfolio by borrower home province (with map coords) -> Filled/geo map + table
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_portfolio_by_province
COMMENT 'Looker Studio: portfolio metrics by borrower home province with map lat/lon.' AS
SELECT
  c.province,
  dp.center_lat                              AS latitude,
  dp.center_lon                              AS longitude,
  CONCAT(dp.center_lat, ',', dp.center_lon)  AS latlong,
  COUNT(l.loan_id)                           AS loans_funded,
  COUNT(DISTINCT l.customer_id)              AS borrowers,
  SUM(l.principal_amount)                    AS total_disbursed_idr,
  SUM(l.outstanding_principal)               AS outstanding_principal_idr,
  ROUND(SUM(CASE WHEN l.dpd >= 90 THEN l.outstanding_principal ELSE 0 END)/NULLIF(SUM(l.outstanding_principal),0),4) AS npl_ratio
FROM {{CATALOG}}.{{SCHEMA}}.fact_loan l
JOIN {{CATALOG}}.{{SCHEMA}}.dim_customer c ON l.customer_id = c.customer_id
JOIN {{CATALOG}}.{{SCHEMA}}.dim_province dp ON c.province = dp.province
GROUP BY c.province, dp.center_lat, dp.center_lon
ORDER BY total_disbursed_idr DESC;

-- 4) Fraud by application-origin province (with map coords) -> Geo bubble map + table
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_fraud_by_province
COMMENT 'Looker Studio: fraud rate/amount by application-origin province with map lat/lon.' AS
SELECT
  s.app_province                             AS province,
  dp.center_lat                              AS latitude,
  dp.center_lon                              AS longitude,
  CONCAT(dp.center_lat, ',', dp.center_lon)  AS latlong,
  COUNT(*)                                    AS applications,
  SUM(CASE WHEN s.is_fraud THEN 1 ELSE 0 END) AS fraud_applications,
  ROUND(AVG(CASE WHEN s.is_fraud THEN 1.0 ELSE 0.0 END),4) AS fraud_rate,
  SUM(CASE WHEN s.is_fraud THEN s.requested_amount ELSE 0 END) AS fraud_amount_idr
FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_signals s
JOIN {{CATALOG}}.{{SCHEMA}}.dim_province dp ON s.app_province = dp.province
GROUP BY s.app_province, dp.center_lat, dp.center_lon
ORDER BY fraud_applications DESC;

-- 5) Fraud hotspots per H3 cell (with map coords) -> Geo bubble map
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_fraud_hotspots
COMMENT 'Looker Studio: geospatial fraud hotspots per H3 res-7 cell with centroid lat/lon.' AS
SELECT
  h3_res7                                    AS h3_cell,
  province,
  cell_lat                                   AS latitude,
  cell_lon                                   AS longitude,
  CONCAT(cell_lat, ',', cell_lon)            AS latlong,
  num_applications                           AS applications,
  num_fraud                                  AS fraud_applications,
  fraud_rate
FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_hotspots;

-- 6) H3 k-ring neighborhood hotspots (smoothed density) -> Weighted bubble map
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_hotspots_kring
COMMENT 'Looker Studio: H3 k-ring neighborhood fraud density for weighted bubble maps.' AS
SELECT
  h3_cell,
  latitude,
  longitude,
  latlong,
  cell_applications                          AS applications,
  kring_applications,
  kring_fraud                                AS fraud_applications,
  kring_fraud_rate                           AS fraud_rate
FROM {{CATALOG}}.{{SCHEMA}}.vw_geo_hotspots_kring;

-- 7) Distance bands (home vs application) -> Bar chart
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_distance_bands
COMMENT 'Looker Studio: fraud rate by home-vs-application distance band.' AS
SELECT distance_band, applications, fraud_applications, fraud_rate, avg_distance_km
FROM {{CATALOG}}.{{SCHEMA}}.vw_geo_distance_bands
ORDER BY band_order;

-- 8) Fraud rings: one device shared across many customers -> Table (ranked)
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_fraud_rings
COMMENT 'Looker Studio: device fraud rings — devices used across >=5 distinct customers, with spatial span.' AS
SELECT
  device_id,
  num_applications,
  num_customers,
  fraud_applications,
  fraud_rate,
  provinces_touched,
  bbox_span_km,
  latlong,
  total_requested_idr
FROM {{CATALOG}}.{{SCHEMA}}.vw_geo_device_ring_clusters;

-- 9) Impossible travel: consecutive applications physically impossible -> Table
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_impossible_travel
COMMENT 'Looker Studio: impossible-travel applications (implied velocity > 400 km/h).' AS
SELECT
  application_id,
  customer_id,
  event_ts,
  prev_event_ts,
  travel_km_from_prev                        AS distance_km,
  hours_from_prev                            AS hours_between,
  implied_speed_kmh,
  province                                   AS home_province,
  app_province                               AS application_province,
  requested_amount                           AS requested_amount_idr,
  device_id,
  ip_country
FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_signals
WHERE impossible_travel_flag = TRUE
ORDER BY implied_speed_kmh DESC;

-- 10) Fraud-rate trend by month -> Time-series line
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_ls_fraud_by_month
COMMENT 'Looker Studio: monthly application volume, fraud count and fraud rate.' AS
SELECT
  DATE_TRUNC('MONTH', application_date)                   AS application_month,
  COUNT(*)                                                AS applications,
  SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)               AS fraud_applications,
  ROUND(AVG(CASE WHEN is_fraud THEN 1.0 ELSE 0.0 END),4)  AS fraud_rate,
  SUM(CASE WHEN is_fraud THEN requested_amount ELSE 0 END) AS fraud_amount_idr
FROM {{CATALOG}}.{{SCHEMA}}.fact_loan_application
GROUP BY DATE_TRUNC('MONTH', application_date)
ORDER BY application_month;
