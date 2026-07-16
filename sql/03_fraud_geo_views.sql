-- geo-fraud-lab :: 03 — GEOSPATIAL FRAUD analytics views.
-- Databricks H3 (h3_*) + ST_* spatial functions on a serverless/Photon SQL warehouse.
-- ST_DistanceSphere returns metres between two point geometries.

-- =====================================================================
-- vw_fraud_signals : per-application geospatial fraud signals
--   - home_distance_km   : app location vs customer home (ST_DistanceSphere)
--   - impossible_travel  : implied speed between a customer's consecutive
--                          applications (LAG over event_ts) exceeds 400 km/h
--   - device ring counts : #applications / #distinct customers per device_id
--   - foreign IP / location mismatch flags + H3 cells
-- =====================================================================
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_fraud_signals AS
WITH app_prov AS (  -- reverse-geocode each application to its ORIGIN province (nearest centroid)
  SELECT application_id, province AS app_province FROM (
    SELECT a.application_id, p.province,
           ROW_NUMBER() OVER (PARTITION BY a.application_id
             ORDER BY ST_DistanceSphere(ST_Point(a.app_lon, a.app_lat),
                                        ST_Point(p.center_lon, p.center_lat))) AS rn
    FROM {{CATALOG}}.{{SCHEMA}}.fact_loan_application a
    CROSS JOIN {{CATALOG}}.{{SCHEMA}}.dim_province p
  ) WHERE rn = 1
),
app AS (
  SELECT
    a.application_id, a.customer_id, a.product_id,
    a.application_date, a.event_ts, a.requested_amount, a.decision,
    a.channel, a.app_lat, a.app_lon, a.device_id, a.ip_country,
    a.h3_res7, a.h3_res9, a.is_fraud, a.fraud_reason,
    c.province, c.city, c.home_lat, c.home_lon, c.credit_score_band,
    ap.app_province
  FROM {{CATALOG}}.{{SCHEMA}}.fact_loan_application a
  JOIN {{CATALOG}}.{{SCHEMA}}.dim_customer c
    ON a.customer_id = c.customer_id
  JOIN app_prov ap ON a.application_id = ap.application_id
),
dev AS (
  SELECT device_id,
         COUNT(*)                    AS device_app_count,
         COUNT(DISTINCT customer_id) AS device_customer_count
  FROM {{CATALOG}}.{{SCHEMA}}.fact_loan_application
  GROUP BY device_id
),
lagged AS (
  SELECT app.*,
         LAG(event_ts) OVER (PARTITION BY customer_id ORDER BY event_ts) AS prev_event_ts,
         LAG(app_lat)  OVER (PARTITION BY customer_id ORDER BY event_ts) AS prev_app_lat,
         LAG(app_lon)  OVER (PARTITION BY customer_id ORDER BY event_ts) AS prev_app_lon
  FROM app
)
SELECT
  l.application_id, l.customer_id, l.product_id, l.application_date, l.event_ts,
  l.requested_amount, l.decision, l.channel, l.province, l.city, l.app_province,
  l.app_lat, l.app_lon, l.home_lat, l.home_lon,
  l.device_id, l.ip_country, l.h3_res7, l.h3_res9,
  l.credit_score_band, l.is_fraud, l.fraud_reason,
  -- distance from home (km)
  ROUND(ST_DistanceSphere(ST_Point(l.app_lon, l.app_lat),
                          ST_Point(l.home_lon, l.home_lat)) / 1000.0, 2) AS home_distance_km,
  -- previous application context (impossible travel)
  l.prev_event_ts,
  ROUND(ST_DistanceSphere(ST_Point(l.app_lon, l.app_lat),
                          ST_Point(l.prev_app_lon, l.prev_app_lat)) / 1000.0, 2) AS travel_km_from_prev,
  ROUND((unix_timestamp(l.event_ts) - unix_timestamp(l.prev_event_ts)) / 3600.0, 2) AS hours_from_prev,
  CASE WHEN l.prev_event_ts IS NOT NULL
            AND (unix_timestamp(l.event_ts) - unix_timestamp(l.prev_event_ts)) > 0
       THEN ROUND(
              (ST_DistanceSphere(ST_Point(l.app_lon, l.app_lat),
                                 ST_Point(l.prev_app_lon, l.prev_app_lat)) / 1000.0)
              / ((unix_timestamp(l.event_ts) - unix_timestamp(l.prev_event_ts)) / 3600.0), 2)
       END AS implied_speed_kmh,
  -- flags
  CASE WHEN l.prev_event_ts IS NOT NULL
            AND (unix_timestamp(l.event_ts) - unix_timestamp(l.prev_event_ts)) > 0
            AND (ST_DistanceSphere(ST_Point(l.app_lon, l.app_lat),
                                   ST_Point(l.prev_app_lon, l.prev_app_lat)) / 1000.0)
                / ((unix_timestamp(l.event_ts) - unix_timestamp(l.prev_event_ts)) / 3600.0) > 400
            AND (ST_DistanceSphere(ST_Point(l.app_lon, l.app_lat),
                                   ST_Point(l.prev_app_lon, l.prev_app_lat)) / 1000.0) > 100
       THEN TRUE ELSE FALSE END AS impossible_travel_flag,
  CASE WHEN ST_DistanceSphere(ST_Point(l.app_lon, l.app_lat),
                              ST_Point(l.home_lon, l.home_lat)) / 1000.0 > 150
       THEN TRUE ELSE FALSE END AS location_mismatch_flag,
  CASE WHEN l.ip_country <> 'ID' THEN TRUE ELSE FALSE END AS foreign_ip_flag,
  d.device_app_count, d.device_customer_count,
  CASE WHEN d.device_customer_count >= 5 THEN TRUE ELSE FALSE END AS device_ring_flag
FROM lagged l
JOIN dev d ON l.device_id = d.device_id;

-- =====================================================================
-- vw_fraud_hotspots : fraud aggregated per H3 res-7 cell (with province + centroid)
--   Centroid lat/lon from h3_centerasgeojson for map plotting.
-- =====================================================================
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_fraud_hotspots AS
SELECT
  h3_res7,
  MAX(app_province)                                                                           AS province,
  ROUND(CAST(get_json_object(h3_centerasgeojson(h3_res7), '$.coordinates[1]') AS DOUBLE), 6)  AS cell_lat,
  ROUND(CAST(get_json_object(h3_centerasgeojson(h3_res7), '$.coordinates[0]') AS DOUBLE), 6)  AS cell_lon,
  COUNT(*)                                                                                    AS num_applications,
  SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)                                                   AS num_fraud,
  ROUND(AVG(CASE WHEN is_fraud THEN 1.0 ELSE 0.0 END), 4)                                      AS fraud_rate
FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_signals
GROUP BY h3_res7
HAVING SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) > 0
ORDER BY num_fraud DESC;
