-- geo-fraud-lab :: 04 — metric-view source: a single APPLICATION-grain base view.
--   application (grain)  ->  fact_loan (1:1 on application_id)  ->  repayment aggregates (1:1 per loan)
-- This avoids repayment fan-out so loan sums are not inflated, while still exposing
-- application, loan and repayment KPIs from one governed source.
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.vw_metric_base AS
WITH repay_agg AS (
  SELECT loan_id,
         SUM(amount_paid)                                    AS repay_paid,
         SUM(installment_amount)                             AS repay_due,
         SUM(CASE WHEN status = 'on_time' THEN 1 ELSE 0 END) AS repay_ontime,
         COUNT(*)                                            AS repay_total
  FROM {{CATALOG}}.{{SCHEMA}}.fact_repayment
  GROUP BY loan_id
),
app_prov AS (
  SELECT application_id, app_province
  FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_signals
)
SELECT
  a.application_id,
  a.customer_id,
  p.product_name,
  c.province,
  ap.app_province,
  c.acquisition_channel,
  c.credit_score_band,
  a.h3_res7,
  a.application_date,
  a.decision,
  a.is_fraud,
  a.requested_amount,
  l.loan_id,
  l.principal_amount,
  l.interest_rate_pa,
  l.status                                  AS loan_status,
  l.outstanding_principal,
  l.dpd,
  l.disbursement_date,
  DATE_TRUNC('MONTH', l.disbursement_date)  AS disbursement_month,
  r.repay_paid,
  r.repay_due,
  r.repay_ontime,
  r.repay_total
FROM {{CATALOG}}.{{SCHEMA}}.fact_loan_application a
JOIN {{CATALOG}}.{{SCHEMA}}.dim_customer c
  ON a.customer_id = c.customer_id
JOIN {{CATALOG}}.{{SCHEMA}}.dim_product p
  ON a.product_id = p.product_id
JOIN app_prov ap
  ON a.application_id = ap.application_id
LEFT JOIN {{CATALOG}}.{{SCHEMA}}.fact_loan l
  ON a.application_id = l.application_id
LEFT JOIN repay_agg r
  ON l.loan_id = r.loan_id;
