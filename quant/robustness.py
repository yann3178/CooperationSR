"""
Robustness tests for Trend-Parity:

  1. Parameter sensitivity (SMA and vol window ±20-50%)
  2. In-sample / out-of-sample 70/30 walk-forward
  3. Sub-period metrics (per 5-year bucket)
  4. Transaction cost stress
  5. Extra: same rules with leverage 1.1x and 1.2x
"""
import numpy as np
import pandas as pd

from framework import compute_metrics, pretty_metrics, run_backtest
from strategy import load_universe, compute_target_weights, ROUND_TRIP_COST


def metrics_for(weights, master, cost=ROUND_TRIP_COST):
    cols = list(weights.columns)
    res = run_backtest(master[cols], weights, cost_roundtrip=cost)
    return res.metrics


print("=" * 80)
print("TREND-PARITY — ROBUSTNESS")
print("=" * 80)

master = load_universe()
base_w = compute_target_weights(master)
base_m = metrics_for(base_w, master)
print(pretty_metrics(base_m, "Base"))

print("\n--- 1) Parameter sensitivity ---")
print("SMA window sweep (base=150):")
for s in [100, 125, 150, 175, 200, 225]:
    w = compute_target_weights(master, sma_n=s)
    m = metrics_for(w, master)
    print(pretty_metrics(m, f"  sma={s}"))

print("\nVol window sweep (base=40):")
for v in [10, 20, 30, 40, 60, 80]:
    w = compute_target_weights(master, vol_n=v)
    m = metrics_for(w, master)
    print(pretty_metrics(m, f"  vol={v}"))

print("\nJoint 20% perturbation:")
for s in [120, 150, 180]:
    for v in [32, 40, 48]:
        w = compute_target_weights(master, sma_n=s, vol_n=v)
        m = metrics_for(w, master)
        print(pretty_metrics(m, f"  sma={s},vol={v}"))

print("\n--- 2) Walk-forward: 70/30 in-sample / out-of-sample ---")
n = len(master)
split = int(n * 0.7)
cut = master.index[split]
print(f"Split at {cut.date()}")

is_master = master.loc[:cut]
os_master = master.loc[cut:]

for sub_name, sub in [("IS 1999-2018", is_master), ("OOS 2018-2026", os_master)]:
    w = compute_target_weights(sub)
    m = metrics_for(w, sub)
    print(pretty_metrics(m, sub_name))
    qm = compute_metrics(sub["QQQ"] / sub["QQQ"].iloc[0])
    print(pretty_metrics(qm, f"{sub_name} QQQ"))

print("\n--- 3) Sub-period metrics (5-year buckets) ---")
years = [1999, 2005, 2010, 2015, 2020, 2026]
eq = pd.Series(dtype=float)
res = run_backtest(master[base_w.columns], base_w,
                   cost_roundtrip=ROUND_TRIP_COST)
eq = res.equity
qeq = master["QQQ"] / master["QQQ"].iloc[0]

for a, b in zip(years[:-1], years[1:]):
    sub = eq.loc[f"{a}":f"{b-1}-12-31"]
    qsub = qeq.loc[f"{a}":f"{b-1}-12-31"]
    if len(sub) < 10:
        continue
    sm = compute_metrics(sub / sub.iloc[0])
    qm = compute_metrics(qsub / qsub.iloc[0])
    print(f"{a}-{b}:")
    print(pretty_metrics(sm, "  Trend-Parity"))
    print(pretty_metrics(qm, "  QQQ"))

print("\n--- 4) Transaction cost stress ---")
for c in [0.0, 0.0005, 0.001, 0.0025, 0.005]:
    m = metrics_for(base_w, master, cost=c)
    print(pretty_metrics(m, f"  cost={c*10000:.0f}bps"))

print("\n--- 5) Mild leverage variants (cash sleeve shorted) ---")
# Apply a scalar >1 to the risky weights, short BIL for the extra.
for lev in [1.0, 1.1, 1.2, 1.3]:
    w = base_w.copy()
    risky = ["QQQ", "IEF", "GLD"]
    w[risky] = w[risky] * lev
    w["BIL"] = 1 - w[risky].sum(axis=1)
    m = metrics_for(w, master)
    print(pretty_metrics(m, f"  lev={lev}"))
