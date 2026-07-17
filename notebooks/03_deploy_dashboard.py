# Databricks notebook source
# DBTITLE 1,Widgets
dbutils.widgets.text("catalog", "main", "1. Catalog")
dbutils.widgets.text("schema", "geo_fraud_lab", "2. Schema")

# COMMAND ----------

# DBTITLE 1,Config
catalog = dbutils.widgets.get("catalog")
schema  = dbutils.widgets.get("schema")
print(f"Target: {catalog}.{schema}")

# COMMAND ----------

# DBTITLE 1,Deploy AI/BI Fraud Dashboard
dashboard_url = None
try:
    import urllib.request
    import requests, json

    _DASH_URL = "https://raw.githubusercontent.com/danteliew6/geo-fraud-lab/main/dashboards/geo_fraud_dashboard.json"
    with urllib.request.urlopen(_DASH_URL) as _r:
        _spec = _r.read().decode("utf-8")

    _spec = _spec.replace("{{CATALOG}}", catalog).replace("{{SCHEMA}}", schema)

    _host = spark.conf.get("spark.databricks.workspaceUrl")
    _token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    _headers = {"Authorization": f"Bearer {_token}", "Content-Type": "application/json"}

    # Auto-detect warehouse (serverless preferred)
    _wh_id = None
    try:
        _wh_resp = requests.get(
            f"https://{_host}/api/2.0/sql/warehouses",
            headers=_headers,
        )
        _wh_resp.raise_for_status()
        _all_wh = _wh_resp.json().get("warehouses", [])
        for _wh in _all_wh:
            if _wh.get("enable_serverless_compute"):
                _wh_id = _wh["id"]
                break
        if not _wh_id and _all_wh:
            _wh_id = _all_wh[0]["id"]
    except Exception:
        pass

    if _wh_id:
        _spec = _spec.replace("{{WAREHOUSE_ID}}", _wh_id)
    else:
        _spec = _spec.replace("{{WAREHOUSE_ID}}", "")

    # Create dashboard
    _resp = requests.post(
        f"https://{_host}/api/2.0/lakeview/dashboards",
        headers=_headers,
        json={"serialized_dashboard": _spec, "display_name": "Geo Fraud Command Center"},
    )
    _resp.raise_for_status()
    _dash_id = _resp.json()["dashboard_id"]

    # Publish dashboard
    _pub_resp = requests.post(
        f"https://{_host}/api/2.0/lakeview/dashboards/{_dash_id}/published",
        headers=_headers,
        json={"embed_credentials": True, "warehouse_id": _wh_id or ""},
    )
    _pub_resp.raise_for_status()

    dashboard_url = f"https://{_host}/dashboardsv3/{_dash_id}/published"
    print(f"Dashboard deployed: {dashboard_url}")

except Exception as _e:
    print(f"Dashboard deploy failed: {_e}")
    print("Tables and views are installed — deploy the dashboard manually via the Databricks UI.")

# COMMAND ----------

# DBTITLE 1,Summary
print(f"Schema: {catalog}.{schema}")
if dashboard_url:
    print(f"AI/BI Dashboard: {dashboard_url}")
