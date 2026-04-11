"""
Variants of the Kevin Davey monthly breakout algorithm.

Tested here:

  V1  Original 5-ETF (SPY/XLF/EEM/GLD/USO), 20% fixed per leg
  V2  Same universe, *equal-weight active* (1/k when k of N are long)
  V3  Extended universe + equal-weight active (add QQQ, TLT, DBC, EFA, IWM)
  V4  V3 with leveraged QQQ substitute (QLD) and 1.2x gross cap
  V5  V3 with per-asset inverse-vol weighting + trend filter
  V6  Blend: 50% Trend-Parity + 50% Davey V3 (ensemble)
  V7  Blend: 50% Trend-Parity + 50% Davey V5

For every run: 10 bps round-trip cost, full history from 2007-01-03.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from framework import (
    load_close, run_backtest, compute_metrics, pretty_metrics, TRADING_DAYS,
)
from davey_strategy import (
    load_davey_universe, davey_monthly_signal, DAVEY_TICKERS, CASH,
    X1, X2, START_DATE,
)
from strategy import load_universe as load_tp_universe, compute_target_weights


master_davey = load_davey_universe()
# Extend with more assets
extra = ["QQQ", "TLT", "IEF", "DBC", "EFA", "IWM", "QLD"]
for tk in extra:
    try:
        s = load_close(tk)
        master_davey[tk] = s.reindex(master_davey.index).ffill()
    except FileNotFoundError:
        pass
# QLD may not exist; build synthetic from QQQ
if "QLD" not in master_davey.columns and "QQQ" in master_davey.columns:
    from framework import build_qld_full
    qld_full = build_qld_full(master_davey["QQQ"])
    master_davey["QLD"] = qld_full.reindex(master_davey.index).ffill()

START = pd.Timestamp("2007-01-03")

def run(weights, label, master=master_davey, start=START):
    cols = list(weights.columns)
    prices = master[cols].loc[start:]
    w = weights.loc[start:]
    res = run_backtest(prices, w, cost_roundtrip=0.001)
    print(pretty_metrics(res.metrics, label))
    return res


def davey_equal_active(master: pd.DataFrame, tickers,
                       x1=X1, x2=X2, max_leverage=1.0) -> pd.DataFrame:
    """Signal-weighted: each active ETF gets 1/k of the budget (capped)."""
    sig = davey_monthly_signal(master[tickers], x1, x2)
    k = sig.sum(axis=1)
    w = sig.div(k.replace(0, np.nan), axis=0).fillna(0.0) * max_leverage
    out = pd.DataFrame(0.0, index=master.index, columns=tickers + [CASH])
    out[tickers] = w
    out[CASH] = 1.0 - out[tickers].sum(axis=1)
    return out


def davey_inv_vol(master: pd.DataFrame, tickers, x1=X1, x2=X2,
                  vol_win=40) -> pd.DataFrame:
    """Weight active ETFs by inverse realised vol (like Trend-Parity)."""
    sig = davey_monthly_signal(master[tickers], x1, x2)
    p = master[tickers]
    vol = p.pct_change().rolling(vol_win).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / vol).where(sig > 0, 0.0).fillna(0.0)
    tot = inv.sum(axis=1)
    w_risk = inv.div(tot.replace(0, np.nan), axis=0).fillna(0.0)
    out = pd.DataFrame(0.0, index=master.index, columns=tickers + [CASH])
    out[tickers] = w_risk
    out[CASH] = 1.0 - out[tickers].sum(axis=1)
    return out


# -----------------------------------------------------------------------
print("\nBenchmarks over 2007-01 → 2026-04:")
qqq = load_close("QQQ").loc[START:]
spy = load_close("SPY").loc[START:]
print(pretty_metrics(compute_metrics(qqq / qqq.iloc[0]), "QQQ B&H"))
print(pretty_metrics(compute_metrics(spy / spy.iloc[0]), "SPY B&H"))

print("\n=== V1: Davey original (5 ETFs, 20% fixed each) ===")
sig = davey_monthly_signal(master_davey[DAVEY_TICKERS])
w_v1 = pd.DataFrame(0.0, index=master_davey.index,
                    columns=DAVEY_TICKERS + [CASH])
w_v1[DAVEY_TICKERS] = sig * 0.2
w_v1[CASH] = 1 - w_v1[DAVEY_TICKERS].sum(axis=1)
run(w_v1, "V1 Davey 20% fixed")

print("\n=== V2: Davey 5-ETF, 1/k equal weight among active ===")
w_v2 = davey_equal_active(master_davey, DAVEY_TICKERS)
run(w_v2, "V2 5-ETF eq-active")

print("\n=== V3: extended universe, 1/k equal weight ===")
U3 = ["SPY", "QQQ", "XLF", "EEM", "EFA", "IWM", "GLD", "TLT", "IEF", "DBC"]
U3 = [t for t in U3 if t in master_davey.columns]
w_v3 = davey_equal_active(master_davey, U3)
run(w_v3, "V3 10-ETF eq-active")

print("\n=== V4: V3 with QLD in place of QQQ (leverage) ===")
U4 = [("QLD" if t == "QQQ" else t) for t in U3]
w_v4 = davey_equal_active(master_davey, U4)
run(w_v4, "V4 10-ETF with QLD")

print("\n=== V5: V3 with inverse-vol weighting ===")
w_v5 = davey_inv_vol(master_davey, U3)
run(w_v5, "V5 inv-vol weighted")

print("\n=== V5b: 5-ETF original with inverse-vol ===")
w_v5b = davey_inv_vol(master_davey, DAVEY_TICKERS)
run(w_v5b, "V5b 5-ETF inv-vol")

print("\n=== V5c: V3 inv-vol but with QLD ===")
w_v5c = davey_inv_vol(master_davey, U4)
run(w_v5c, "V5c inv-vol + QLD")

# -----------------------------------------------------------------------
# Ensemble: Trend-Parity + Davey
# -----------------------------------------------------------------------
print("\n=== Ensemble: 50% Trend-Parity + 50% Davey variants ===")
tp_master = load_tp_universe()
tp_w = compute_target_weights(tp_master)   # has QQQ/IEF/GLD/BIL

# Build a common frame: union of tp_master and master_davey columns
cols_all = sorted(set(tp_master.columns) | set(master_davey.columns))
idx = master_davey.index
common = pd.DataFrame(index=idx, columns=cols_all, dtype=float)
for c in cols_all:
    if c in master_davey.columns:
        common[c] = master_davey[c]
    elif c in tp_master.columns:
        common[c] = tp_master[c].reindex(idx).ffill()
common = common.ffill()

# Reindex TP weights and Davey weights onto common frame
def blend(wa, wb, alpha=0.5):
    all_cols = sorted(set(wa.columns) | set(wb.columns))
    a = wa.reindex(columns=all_cols, fill_value=0.0)
    b = wb.reindex(columns=all_cols, fill_value=0.0)
    return alpha * a + (1 - alpha) * b


tp_w_on_idx = tp_w.reindex(idx).ffill().fillna(0.0)

for label, wb in [("Davey V2", w_v2), ("Davey V3", w_v3),
                  ("Davey V5", w_v5), ("Davey V5c", w_v5c)]:
    w_ens = blend(tp_w_on_idx, wb, 0.5)
    prices = common[list(w_ens.columns)].ffill()
    # keep rows where at least TP data is present (from 1999-03)
    w_ens = w_ens.loc[START:]
    prices_bt = prices.loc[START:]
    res = run_backtest(prices_bt, w_ens, cost_roundtrip=0.001)
    print(pretty_metrics(res.metrics, f"50/50 TP + {label}"))

# -----------------------------------------------------------------------
# Alternate blend ratios
# -----------------------------------------------------------------------
print("\nBlend ratios TP / Davey-V5 (inv-vol, 10-ETF, extended universe)")
for alpha in [0.0, 0.25, 0.5, 0.75, 1.0]:
    w_ens = blend(tp_w_on_idx, w_v5, alpha)
    prices = common[list(w_ens.columns)].ffill().loc[START:]
    w_ens = w_ens.loc[START:]
    res = run_backtest(prices, w_ens, cost_roundtrip=0.001)
    print(pretty_metrics(res.metrics,
          f"alpha_TP={alpha:.2f}"))

# Same thing: TP + Davey V5c (with QLD) + maybe leverage
print("\nBlend ratios TP / Davey-V5c (inv-vol + QLD)")
for alpha in [0.0, 0.25, 0.5, 0.75, 1.0]:
    w_ens = blend(tp_w_on_idx, w_v5c, alpha)
    prices = common[list(w_ens.columns)].ffill().loc[START:]
    w_ens = w_ens.loc[START:]
    res = run_backtest(prices, w_ens, cost_roundtrip=0.001)
    print(pretty_metrics(res.metrics, f"alpha_TP={alpha:.2f}"))
