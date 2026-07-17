# Databricks notebook source
# DBTITLE 1,Widgets
dbutils.widgets.text("catalog", "main", "1. Catalog (must exist)")
dbutils.widgets.text("schema", "geo_fraud_lab", "2. Schema to create")

# COMMAND ----------

# DBTITLE 1,Config
catalog = dbutils.widgets.get("catalog")
schema  = dbutils.widgets.get("schema")

if not catalog:
    raise ValueError("catalog widget is empty — set it above and re-run.")

print(f"Target: {catalog}.{schema}")

# COMMAND ----------

# DBTITLE 1,Ensure pandas / numpy available
import subprocess, sys
try:
    import pandas, numpy
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pandas", "numpy"])

# COMMAND ----------

# DBTITLE 1,Inline data generator (from scripts/generate_data.py)
from __future__ import annotations
import numpy as np
import pandas as pd

SEED = 42
N_CUST = 20_000
N_APP = 30_000
N_LOAN = 18_000
REPAY_TARGET = 200_000

PROVINCES = [
    ("DKI Jakarta",     "Jakarta",        -6.2088, 106.8456, 0.18),
    ("West Java",       "Bandung",        -6.9175, 107.6191, 0.15),
    ("Central Java",    "Semarang",       -6.9667, 110.4167, 0.10),
    ("East Java",       "Surabaya",       -7.2575, 112.7521, 0.12),
    ("Banten",          "Serang",         -6.1200, 106.1503, 0.06),
    ("Yogyakarta",      "Yogyakarta",     -7.7956, 110.3695, 0.04),
    ("North Sumatra",   "Medan",           3.5952,  98.6722, 0.06),
    ("South Sumatra",   "Palembang",      -2.9761, 104.7754, 0.04),
    ("West Sumatra",    "Padang",         -0.9471, 100.4172, 0.03),
    ("Riau",            "Pekanbaru",       0.5071, 101.4478, 0.03),
    ("Lampung",         "Bandar Lampung", -5.3971, 105.2668, 0.03),
    ("Bali",            "Denpasar",       -8.6705, 115.2126, 0.04),
    ("South Sulawesi",  "Makassar",       -5.1477, 119.4327, 0.04),
    ("North Sulawesi",  "Manado",          1.4748, 124.8421, 0.02),
    ("East Kalimantan", "Samarinda",      -0.5022, 117.1536, 0.03),
    ("West Kalimantan", "Pontianak",      -0.0263, 109.3425, 0.03),
]

PRODUCT_NAME = "Personal Cash Loan"

FIRST_M = ["Budi", "Agus", "Andi", "Dedi", "Eko", "Rizki", "Bayu", "Dwi", "Fajar", "Hendra",
           "Joko", "Rudi", "Slamet", "Wahyu", "Yusuf", "Ahmad", "Bambang", "Cahyo", "Dimas", "Ferry"]
FIRST_F = ["Siti", "Dewi", "Sri", "Ani", "Rina", "Wati", "Fitri", "Indah", "Lestari", "Maya",
           "Nur", "Putri", "Ratna", "Sari", "Yuni", "Ayu", "Citra", "Dian", "Endah", "Wulan"]
LAST = ["Santoso", "Wijaya", "Kusuma", "Pratama", "Nugroho", "Saputra", "Hidayat", "Setiawan",
        "Halim", "Gunawan", "Wibowo", "Susanto", "Purnama", "Ramadhan", "Utomo", "Firmansyah",
        "Maulana", "Prasetyo", "Suryadi", "Handoko"]


def _generate():
    rng = np.random.default_rng(SEED)

    prov_names = np.array([p[0] for p in PROVINCES])
    prov_city  = {p[0]: p[1] for p in PROVINCES}
    prov_lat   = {p[0]: p[2] for p in PROVINCES}
    prov_lon   = {p[0]: p[3] for p in PROVINCES}
    prov_w     = np.array([p[4] for p in PROVINCES], dtype=float)
    prov_w     = prov_w / prov_w.sum()

    # dim_customer
    cust_id   = np.array([f"CUST{100000 + i}" for i in range(N_CUST)])
    home_prov = rng.choice(prov_names, size=N_CUST, p=prov_w)
    gender    = rng.choice(["Male", "Female"], size=N_CUST, p=[0.55, 0.45])
    first = np.where(
        gender == "Male",
        np.array(FIRST_M)[rng.integers(0, len(FIRST_M), N_CUST)],
        np.array(FIRST_F)[rng.integers(0, len(FIRST_F), N_CUST)],
    )
    last      = np.array(LAST)[rng.integers(0, len(LAST), N_CUST)]
    full_name = np.char.add(np.char.add(first, " "), last)
    home_city = np.array([prov_city[p] for p in home_prov])
    base_lat  = np.array([prov_lat[p]  for p in home_prov])
    base_lon  = np.array([prov_lon[p]  for p in home_prov])
    home_lat  = np.round(base_lat + rng.normal(0, 0.10, N_CUST), 6)
    home_lon  = np.round(base_lon + rng.normal(0, 0.10, N_CUST), 6)
    age           = rng.integers(21, 60, N_CUST)
    income_band   = rng.choice(["<3jt", "3-5jt", "5-10jt", "10jt+"], size=N_CUST, p=[0.30, 0.38, 0.24, 0.08])
    employment    = rng.choice(["Salaried", "Self-Employed", "Freelancer", "Civil Servant"],
                               size=N_CUST, p=[0.45, 0.28, 0.17, 0.10])
    credit_band   = rng.choice(["Poor", "Fair", "Good", "Excellent"], size=N_CUST, p=[0.18, 0.37, 0.33, 0.12])
    acq_channel   = rng.choice(["Mobile App", "Web", "Agent", "Referral", "Marketplace"],
                               size=N_CUST, p=[0.50, 0.20, 0.12, 0.10, 0.08])
    kyc           = rng.choice(["Verified", "Pending", "Rejected"], size=N_CUST, p=[0.88, 0.08, 0.04])
    join_start    = np.datetime64("2022-01-01")
    join_span     = (np.datetime64("2025-06-30") - join_start).astype(int)
    join_date     = join_start + rng.integers(0, join_span, N_CUST).astype("timedelta64[D]")

    dim_customer = pd.DataFrame({
        "customer_id": cust_id, "full_name": full_name, "province": home_prov, "city": home_city,
        "home_lat": home_lat, "home_lon": home_lon, "age": age, "gender": gender,
        "income_band": income_band, "employment_type": employment, "credit_score_band": credit_band,
        "acquisition_channel": acq_channel, "kyc_status": kyc,
        "join_date": pd.to_datetime(join_date),
    })

    # dim_product
    tenors      = [6, 9, 12, 15, 18, 24]
    rates       = [0.36, 0.40, 0.42, 0.44, 0.46, 0.48]
    dim_product = pd.DataFrame({
        "product_id":       [f"PROD{t:02d}" for t in tenors],
        "product_name":     [PRODUCT_NAME] * len(tenors),
        "tenor_months":     tenors,
        "interest_rate_pa": rates,
        "min_amount":       [2_000_000] * len(tenors),
        "max_amount":       [20_000_000] * len(tenors),
    })
    prod_ids = dim_product["product_id"].to_numpy()

    # dim_date
    dstart, dend = np.datetime64("2023-01-01"), np.datetime64("2025-12-31")
    days         = pd.date_range(dstart, dend, freq="D")
    dim_date = pd.DataFrame({
        "date_key":     [int(d.strftime("%Y%m%d")) for d in days],
        "calendar_date": days,
        "day": days.day, "month": days.month, "quarter": days.quarter, "year": days.year,
        "month_name":   days.strftime("%B"),
        "day_of_week":  days.strftime("%A"),
        "is_weekend":   days.dayofweek >= 5,
        "year_month":   days.strftime("%Y-%m"),
    })

    # fact_loan_application
    app_cust_idx     = rng.integers(0, N_CUST, N_APP)
    app_id           = np.array([f"APP{500000 + i}" for i in range(N_APP)])
    app_prod         = rng.choice(prod_ids, size=N_APP)
    astart           = np.datetime64("2023-01-01T00:00:00")
    aspan            = int((np.datetime64("2025-12-15T00:00:00") - astart) / np.timedelta64(1, "s"))
    app_ts_sec       = rng.integers(0, aspan, N_APP)
    event_ts         = astart + app_ts_sec.astype("timedelta64[s]")
    requested_amount = (rng.integers(2, 21, N_APP) * 1_000_000).astype(np.int64)
    c_home_lat       = home_lat[app_cust_idx]
    c_home_lon       = home_lon[app_cust_idx]
    app_lat          = c_home_lat + rng.normal(0, 0.06, N_APP)
    app_lon          = c_home_lon + rng.normal(0, 0.06, N_APP)
    device_id        = np.array([f"DEV{rng.integers(10 ** 9, 10 ** 10)}" for _ in range(N_APP)])
    ip_country       = np.full(N_APP, "ID", dtype=object)
    is_fraud         = np.zeros(N_APP, dtype=bool)
    fraud_reason     = np.full(N_APP, None, dtype=object)

    # device_ring
    N_RING      = 15
    ring_devices = np.array([f"DEVRING{i:04d}" for i in range(N_RING)])
    ring_idx    = rng.choice(N_APP, size=int(N_APP * 0.012), replace=False)
    device_id[ring_idx]   = ring_devices[rng.integers(0, N_RING, len(ring_idx))]
    is_fraud[ring_idx]    = True
    fraud_reason[ring_idx] = "device_ring"

    # location_mismatch
    mis_idx   = rng.choice(np.setdiff1d(np.arange(N_APP), ring_idx),
                           size=int(N_APP * 0.010), replace=False)
    far_prov  = rng.choice(prov_names, size=len(mis_idx))
    app_lat[mis_idx] = np.array([prov_lat[p] for p in far_prov]) + rng.normal(0, 0.08, len(mis_idx))
    app_lon[mis_idx] = np.array([prov_lon[p] for p in far_prov]) + rng.normal(0, 0.08, len(mis_idx))
    is_fraud[mis_idx]    = True
    fraud_reason[mis_idx] = "location_mismatch"

    # foreign_ip
    avail   = np.setdiff1d(np.arange(N_APP), np.concatenate([ring_idx, mis_idx]))
    fip_idx = rng.choice(avail, size=int(N_APP * 0.005), replace=False)
    ip_country[fip_idx] = rng.choice(["SG", "MY", "PH", "VN", "CN", "RU"], size=len(fip_idx))
    far_prov2 = rng.choice(prov_names, size=len(fip_idx))
    app_lat[fip_idx] = np.array([prov_lat[p] for p in far_prov2]) + rng.normal(0, 0.1, len(fip_idx))
    app_lon[fip_idx] = np.array([prov_lon[p] for p in far_prov2]) + rng.normal(0, 0.1, len(fip_idx))
    is_fraud[fip_idx]    = True
    fraud_reason[fip_idx] = "foreign_ip"

    # geo_hotspot
    avail   = np.setdiff1d(np.arange(N_APP), np.flatnonzero(is_fraud))
    hot_idx = rng.choice(avail, size=int(N_APP * 0.005), replace=False)
    hot_prov = rng.choice(["DKI Jakarta", "North Sumatra"], size=len(hot_idx), p=[0.6, 0.4])
    app_lat[hot_idx] = np.array([prov_lat[p] for p in hot_prov]) + rng.normal(0, 0.03, len(hot_idx))
    app_lon[hot_idx] = np.array([prov_lon[p] for p in hot_prov]) + rng.normal(0, 0.03, len(hot_idx))
    is_fraud[hot_idx]    = True
    fraud_reason[hot_idx] = "geo_hotspot"

    # impossible_travel
    avail   = np.setdiff1d(np.arange(N_APP), np.flatnonzero(is_fraud))
    n_pairs = 120
    pair_pool = rng.choice(avail, size=n_pairs * 2, replace=False)
    it_first  = pair_pool[:n_pairs]
    it_second = pair_pool[n_pairs:]
    for a, b in zip(it_first, it_second):
        c = app_cust_idx[a]
        app_cust_idx[b] = c
        app_lat[a] = home_lat[c] + rng.normal(0, 0.03)
        app_lon[a] = home_lon[c] + rng.normal(0, 0.03)
        far_p = rng.choice(prov_names)
        if far_p == home_prov[c]:
            far_p = "Bali" if home_prov[c] != "Bali" else "North Sumatra"
        app_lat[b] = prov_lat[far_p] + rng.normal(0, 0.05)
        app_lon[b] = prov_lon[far_p] + rng.normal(0, 0.05)
        gap_sec    = int(rng.integers(1800, 3 * 3600))
        event_ts[b] = event_ts[a] + np.timedelta64(gap_sec, "s")
    is_fraud[it_second]    = True
    fraud_reason[it_second] = "impossible_travel"

    application_date = event_ts.astype("datetime64[D]")
    app_lat = np.round(app_lat, 6)
    app_lon = np.round(app_lon, 6)

    cust_credit = credit_band[app_cust_idx]
    approve_p   = np.select(
        [cust_credit == "Excellent", cust_credit == "Good",
         cust_credit == "Fair",      cust_credit == "Poor"],
        [0.90, 0.78, 0.60, 0.35], default=0.65)
    approve_p = np.where(is_fraud, approve_p * 0.5, approve_p)
    approved  = rng.random(N_APP) < approve_p
    decision  = np.where(approved, "approved", "rejected")
    decision_date = (application_date + rng.integers(0, 5, N_APP).astype("timedelta64[D]"))
    rej_reasons   = ["Low credit score", "Insufficient income", "Failed KYC", "Fraud suspected",
                     "High existing debt", "Incomplete documents"]
    rejection_reason = np.where(
        approved, None,
        np.where(is_fraud, "Fraud suspected",
                 np.array(rej_reasons)[rng.integers(0, len(rej_reasons), N_APP)]))
    app_channel = acq_channel[app_cust_idx]

    fact_loan_application = pd.DataFrame({
        "application_id":  app_id,
        "customer_id":     cust_id[app_cust_idx],
        "product_id":      app_prod,
        "application_date": pd.to_datetime(application_date),
        "event_ts":        pd.to_datetime(event_ts),
        "requested_amount": requested_amount,
        "decision":        decision,
        "decision_date":   pd.to_datetime(decision_date),
        "rejection_reason": rejection_reason,
        "channel":         app_channel,
        "app_lat":         app_lat,
        "app_lon":         app_lon,
        "device_id":       device_id,
        "ip_country":      ip_country.astype(str),
        "h3_res7":         pd.Series([None] * N_APP, dtype="object"),
        "h3_res9":         pd.Series([None] * N_APP, dtype="object"),
        "is_fraud":        is_fraud,
        "fraud_reason":    fraud_reason,
    })

    # fact_loan
    approved_pos = np.flatnonzero(approved)
    fund_pos     = rng.choice(approved_pos, size=min(N_LOAN, len(approved_pos)), replace=False)
    NL           = len(fund_pos)
    loan_id      = np.array([f"LOAN{700000 + i}" for i in range(NL)])
    l_app_id     = app_id[fund_pos]
    l_cust       = cust_id[app_cust_idx][fund_pos]
    l_prod       = app_prod[fund_pos]
    disb_date    = (decision_date[fund_pos] + rng.integers(1, 7, NL).astype("timedelta64[D]"))
    principal    = requested_amount[fund_pos]
    prod_tenor   = dict(zip(dim_product.product_id, dim_product.tenor_months))
    prod_rate    = dict(zip(dim_product.product_id, dim_product.interest_rate_pa))
    l_tenor      = np.array([prod_tenor[p] for p in l_prod])
    l_rate       = np.array([prod_rate[p]  for p in l_prod])

    status = rng.choice(["current", "paid_off", "delinquent", "default", "written_off"],
                        size=NL, p=[0.62, 0.28, 0.055, 0.03, 0.015])
    l_is_fraud = is_fraud[fund_pos]
    status = np.where(l_is_fraud & (rng.random(NL) < 0.6),
                      rng.choice(["default", "written_off"], size=NL, p=[0.5, 0.5]), status)

    dpd = np.select(
        [status == "current",    status == "paid_off",    status == "delinquent",
         status == "default",    status == "written_off"],
        [rng.integers(0, 8, NL), np.zeros(NL, int), rng.integers(15, 89, NL),
         rng.integers(90, 180, NL), rng.integers(181, 365, NL)], default=0)
    frac_paid   = np.clip(rng.beta(2, 2, NL), 0, 1)
    outstanding = np.where(status == "paid_off", 0,
                           np.round(principal * (1 - frac_paid * 0.9)).astype(np.int64))
    outstanding = np.where(status == "written_off", 0, outstanding).astype(np.int64)

    fact_loan = pd.DataFrame({
        "loan_id":              loan_id,
        "application_id":       l_app_id,
        "customer_id":          l_cust,
        "product_id":           l_prod,
        "disbursement_date":    pd.to_datetime(disb_date),
        "principal_amount":     principal,
        "tenor_months":         l_tenor,
        "interest_rate_pa":     l_rate,
        "status":               status,
        "outstanding_principal": outstanding,
        "dpd":                  dpd.astype(int),
    })

    # fact_repayment
    TODAY       = np.datetime64("2025-12-15")
    rows        = []
    rep_counter = 800000
    for i in range(NL):
        p = int(principal[i]); t = int(l_tenor[i]); r = float(l_rate[i])
        total_due  = p * (1 + r * t / 12.0)
        inst       = round(total_due / t)
        prin_comp  = round(p / t)
        int_comp   = inst - prin_comp
        disb       = disb_date[i]
        months_elapsed = int((TODAY - disb) / np.timedelta64(30, "D"))
        n_inst     = min(t, max(0, months_elapsed))
        st         = status[i]
        for k in range(1, n_inst + 1):
            due = disb + np.timedelta64(30 * k, "D")
            if st == "paid_off":
                rst = "on_time"
            elif st == "current":
                rst = "on_time" if rng.random() < 0.93 else "late"
            elif st == "delinquent":
                rst = rng.choice(["on_time", "late", "missed"], p=[0.5, 0.3, 0.2])
            elif st in ("default", "written_off"):
                rst = "on_time" if k <= n_inst * 0.5 and rng.random() < 0.7 else \
                      rng.choice(["late", "missed"], p=[0.3, 0.7])
            else:
                rst = "on_time"
            if rst == "on_time":
                paid = due + np.timedelta64(int(rng.integers(0, 3)), "D")
                amt  = inst
            elif rst == "late":
                paid = due + np.timedelta64(int(rng.integers(5, 45)), "D")
                amt  = inst
            else:
                paid = np.datetime64("NaT", "D")
                amt  = 0
            rows.append((f"REP{rep_counter}", loan_id[i], due, paid, inst, prin_comp, int_comp, amt, rst))
            rep_counter += 1
        if len(rows) >= REPAY_TARGET + 50_000:
            break

    if len(rows) > REPAY_TARGET:
        rows = rows[:REPAY_TARGET]

    fact_repayment = pd.DataFrame(rows, columns=[
        "repayment_id", "loan_id", "due_date", "paid_date", "installment_amount",
        "principal_component", "interest_component", "amount_paid", "status"])
    fact_repayment["due_date"]  = pd.to_datetime(fact_repayment["due_date"])
    fact_repayment["paid_date"] = pd.to_datetime(fact_repayment["paid_date"])

    return {
        "dim_customer":          dim_customer,
        "dim_product":           dim_product,
        "dim_date":              dim_date,
        "fact_loan_application": fact_loan_application,
        "fact_loan":             fact_loan,
        "fact_repayment":        fact_repayment,
    }

# COMMAND ----------

# DBTITLE 1,Create schema
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")
print(f"Schema {catalog}.{schema} ready")

# COMMAND ----------

# DBTITLE 1,Generate and write tables
print("Generating synthetic dataset (fixed seed)...")
tables = _generate()

print("Row counts:")
for name, df in tables.items():
    print(f"  {name:<22}: {len(df):,}")

app_df = tables["fact_loan_application"]
print(f"Fraud apps: {int(app_df['is_fraud'].sum()):,} ({app_df['is_fraud'].mean() * 100:.2f}%)")

print("\nWriting to Unity Catalog...")
for table_name, df in tables.items():
    spark_df  = spark.createDataFrame(df)
    full_name = f"`{catalog}`.`{schema}`.`{table_name}`"
    spark_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(full_name)
    print(f"  {full_name}: {len(df):,} rows written")

print("Base tables written successfully")
