-- geo-fraud-lab :: 05 — Unity Catalog Metric View (governed semantic layer).
-- Source = application-grain base view (vw_metric_base). Query with MEASURE().
CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.metrics_lending
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {{CATALOG}}.{{SCHEMA}}.vw_metric_base
comment: "Digital consumer-lending KPIs — portfolio, credit risk (NPL/PAR), collections, approvals and geospatial fraud. Governed semantic layer consumed by BI tools such as Looker Studio."
dimensions:
  - name: Province
    expr: province
    comment: "Borrower home province"
  - name: Application Province
    expr: app_province
    comment: "Province where the application originated (reverse-geocoded)"
  - name: Product Name
    expr: product_name
  - name: Acquisition Channel
    expr: acquisition_channel
  - name: Credit Score Band
    expr: credit_score_band
  - name: Disbursement Month
    expr: disbursement_month
    comment: "Month the loan was disbursed"
  - name: Loan Status
    expr: loan_status
  - name: H3 Cell
    expr: h3_res7
    comment: "H3 resolution-7 cell of the application location"
measures:
  - name: total_disbursed
    expr: SUM(principal_amount)
    comment: "Total principal disbursed (IDR)"
  - name: num_loans_funded
    expr: COUNT(loan_id)
  - name: active_borrowers
    expr: COUNT(DISTINCT CASE WHEN loan_status IN ('current','delinquent') THEN customer_id END)
  - name: avg_loan_size
    expr: AVG(principal_amount)
  - name: total_outstanding_principal
    expr: SUM(outstanding_principal)
  - name: npl_ratio
    expr: SUM(CASE WHEN dpd >= 90 THEN outstanding_principal ELSE 0 END) / NULLIF(SUM(outstanding_principal), 0)
    comment: "Non-performing (dpd>=90) outstanding / total outstanding"
  - name: par30
    expr: SUM(CASE WHEN dpd > 30 THEN outstanding_principal ELSE 0 END) / NULLIF(SUM(outstanding_principal), 0)
    comment: "Portfolio-at-risk 30+ dpd"
  - name: par90
    expr: SUM(CASE WHEN dpd >= 90 THEN outstanding_principal ELSE 0 END) / NULLIF(SUM(outstanding_principal), 0)
    comment: "Portfolio-at-risk 90+ dpd"
  - name: approval_rate
    expr: AVG(CASE WHEN decision = 'approved' THEN 1.0 ELSE 0.0 END)
  - name: collection_rate
    expr: SUM(repay_paid) / NULLIF(SUM(repay_due), 0)
    comment: "Amount collected / amount due across installments"
  - name: avg_interest_rate
    expr: AVG(interest_rate_pa)
  - name: fraud_rate
    expr: AVG(CASE WHEN is_fraud THEN 1.0 ELSE 0.0 END)
    comment: "Share of applications flagged fraudulent"
  - name: fraud_amount
    expr: SUM(CASE WHEN is_fraud THEN requested_amount ELSE 0 END)
    comment: "Requested amount on fraudulent applications (IDR)"
  - name: num_flagged_applications
    expr: SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)
$$;
