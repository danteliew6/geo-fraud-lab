-- geo-fraud-lab :: 01 — compute H3 geospatial index + table/column comments.
-- Databricks H3: h3_longlatash3string(lon, lat, resolution). Requires a
-- Photon-enabled / serverless SQL warehouse.
-- Tokens {{CATALOG}} and {{SCHEMA}} are substituted at install time.

-- Rebuild fact_loan_application with H3 res7 / res9 derived from app_lon/app_lat.
CREATE OR REPLACE TABLE {{CATALOG}}.{{SCHEMA}}.fact_loan_application AS
SELECT
  application_id,
  customer_id,
  product_id,
  application_date,
  event_ts,
  requested_amount,
  decision,
  decision_date,
  rejection_reason,
  channel,
  app_lat,
  app_lon,
  device_id,
  ip_country,
  h3_longlatash3string(app_lon, app_lat, 7) AS h3_res7,
  h3_longlatash3string(app_lon, app_lat, 9) AS h3_res9,
  is_fraud,
  fraud_reason
FROM {{CATALOG}}.{{SCHEMA}}.fact_loan_application;

-- ---------- Table comments ----------
COMMENT ON TABLE {{CATALOG}}.{{SCHEMA}}.dim_customer IS 'Borrower master: demographics, KYC, credit band, acquisition channel and home geolocation (home_lat/home_lon) used as the geospatial baseline for fraud distance checks.';
COMMENT ON TABLE {{CATALOG}}.{{SCHEMA}}.dim_product IS 'Personal cash-loan product catalog — one row per tenor (6-24 months) with annual interest rate and min/max loan amount (IDR 2,000,000 - 20,000,000).';
COMMENT ON TABLE {{CATALOG}}.{{SCHEMA}}.dim_date IS 'Calendar dimension 2023-01-01 to 2025-12-31 for time-based portfolio and fraud trend analysis.';
-- (dim_province is created with its comment in 02_dim_province.sql)
COMMENT ON TABLE {{CATALOG}}.{{SCHEMA}}.fact_loan_application IS 'Loan applications with decision outcome and GEOSPATIAL fraud signals: application geolocation (app_lat/app_lon), H3 cells (res7/res9), device_id, ip_country and is_fraud/fraud_reason driven by impossible-travel, location-mismatch, device rings, foreign IP and geo hotspots.';
COMMENT ON TABLE {{CATALOG}}.{{SCHEMA}}.fact_loan IS 'Funded (disbursed) loans with principal, tenor, rate, repayment status, outstanding principal and days-past-due (dpd) for portfolio / NPL / PAR analysis.';
COMMENT ON TABLE {{CATALOG}}.{{SCHEMA}}.fact_repayment IS 'Installment-level repayment schedule and behavior (on_time / late / missed) with principal and interest components for collection-rate analysis.';

-- ---------- dim_customer column comments ----------
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.dim_customer.customer_id IS 'Unique customer identifier (PK).';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.dim_customer.home_lat IS 'Home latitude (WGS84) — geospatial baseline for fraud distance checks.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.dim_customer.home_lon IS 'Home longitude (WGS84) — geospatial baseline for fraud distance checks.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.dim_customer.credit_score_band IS 'Credit risk band: Poor / Fair / Good / Excellent.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.dim_customer.kyc_status IS 'KYC verification state: Verified / Pending / Rejected.';

-- ---------- fact_loan_application column comments ----------
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan_application.app_lat IS 'Application latitude (WGS84) at time of submission.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan_application.app_lon IS 'Application longitude (WGS84) at time of submission.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan_application.h3_res7 IS 'H3 index (resolution 7, ~5km cell) of the application location — coarse geo-hotspot grouping.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan_application.h3_res9 IS 'H3 index (resolution 9, ~175m cell) of the application location — fine geo-hotspot grouping.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan_application.device_id IS 'Device fingerprint — DEVRING* ids are shared across many applications (fraud rings).';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan_application.ip_country IS 'ISO country of the originating IP — non-ID values are a fraud signal.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan_application.is_fraud IS 'Ground-truth fraud flag (geospatially driven) for lab scoring.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan_application.fraud_reason IS 'Fraud typology: impossible_travel | location_mismatch | device_ring | foreign_ip | geo_hotspot.';

-- ---------- fact_loan column comments ----------
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan.status IS 'Loan status: current | paid_off | delinquent | default | written_off.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan.dpd IS 'Days past due — drives PAR30 / PAR90 and NPL classification.';
COMMENT ON COLUMN {{CATALOG}}.{{SCHEMA}}.fact_loan.outstanding_principal IS 'Remaining principal balance (IDR).';
