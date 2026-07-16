-- geo-fraud-lab :: 08 — verification: every table + view runs on the warehouse.
SELECT 'dim_customer' AS obj, COUNT(*) n FROM {{CATALOG}}.{{SCHEMA}}.dim_customer
UNION ALL SELECT 'dim_product', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.dim_product
UNION ALL SELECT 'dim_date', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.dim_date
UNION ALL SELECT 'dim_province', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.dim_province
UNION ALL SELECT 'fact_loan_application', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.fact_loan_application
UNION ALL SELECT 'fact_loan', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.fact_loan
UNION ALL SELECT 'fact_repayment', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.fact_repayment
UNION ALL SELECT 'vw_fraud_signals', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_signals
UNION ALL SELECT 'vw_fraud_hotspots', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_fraud_hotspots
UNION ALL SELECT 'vw_metric_base', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_metric_base
UNION ALL SELECT 'vw_geo_hotspots_kring', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_geo_hotspots_kring
UNION ALL SELECT 'vw_geo_province_choropleth', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_geo_province_choropleth
UNION ALL SELECT 'vw_geo_distance_bands', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_geo_distance_bands
UNION ALL SELECT 'vw_geo_device_ring_clusters', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_geo_device_ring_clusters
UNION ALL SELECT 'vw_ls_portfolio_overview', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_portfolio_overview
UNION ALL SELECT 'vw_ls_disbursement_by_month', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_disbursement_by_month
UNION ALL SELECT 'vw_ls_portfolio_by_province', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_portfolio_by_province
UNION ALL SELECT 'vw_ls_fraud_by_province', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_fraud_by_province
UNION ALL SELECT 'vw_ls_fraud_hotspots', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_fraud_hotspots
UNION ALL SELECT 'vw_ls_hotspots_kring', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_hotspots_kring
UNION ALL SELECT 'vw_ls_distance_bands', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_distance_bands
UNION ALL SELECT 'vw_ls_fraud_rings', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_fraud_rings
UNION ALL SELECT 'vw_ls_impossible_travel', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_impossible_travel
UNION ALL SELECT 'vw_ls_fraud_by_month', COUNT(*) FROM {{CATALOG}}.{{SCHEMA}}.vw_ls_fraud_by_month
ORDER BY obj;
