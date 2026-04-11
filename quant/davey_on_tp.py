"""
Apples-to-apples: swap Trend-Parity's SMA150 filter for Kevin Davey's
monthly 4/5 breakout, keeping everything else identical.

Also tests the same substitution on the extended 6-asset universe.

Also reports Davey-only performance on Trend-Parity's *universe*
(QQQ/IEF/GLD), which is the fairest comparison to the original paper.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from framework import (
    load_close, run_backtest, compute_metrics, pretty_metrics, TRADING_DAYS,
)
from davey_strategy import davey_monthly_signal, CASH, X1, X2, START_DATE
from strategy import load_universe as load_tp_universe


master = load_tp_universe()    # QQQ, IEF, GLD, BIL

print(f"Master: {master.index[0].date()} -> {master.index[-1].date()}")

# Bounds
START_FULL = master.index[0]                   # 1999-03
START_DAVEY = pd.Timestamp("2007-01-03")       # Davey's original start


def davey_inv_vol_weights(universe, vol_win=40, x1=X1, x2=X2, leverage=1.0):
    """Inverse-vol weighted, gated by Davey monthly breakout signal."""
    sig = davey_monthly_signal(master[universe], x1, x2)
    p = master[universe]
    vol = p.pct_change().rolling(vol_win).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / vol).where(sig > 0, 0.0).fillna(0.0)
    tot = inv.sum(axis=1)
    w_risk = inv.div(tot.replace(0, np.nan), axis=0).fillna(0.0) * leverage
    out = pd.DataFrame(0.0, index=master.index, columns=universe + [CASH])
    out[universe] = w_risk
    out[CASH] = 1.0 - out[universe].sum(axis=1)
    return out


def sma_inv_vol_weights(universe, sma_n=150, vol_win=40, leverage=1.0):
    """The original Trend-Parity gating logic (for reference)."""
    p = master[universe]
    trend = p.gt(p.rolling(sma_n).mean())
    vol = p.pct_change().rolling(vol_win).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / vol).where(trend, 0.0).fillna(0.0)
    tot = inv.sum(axis=1)
    w = inv.div(tot.replace(0, np.nan), axis=0).fillna(0.0) * leverage
    out = pd.DataFrame(0.0, index=master.index, columns=universe + [CASH])
    out[universe] = w
    out[CASH] = 1.0 - out[universe].sum(axis=1)
    # monthly rebalance (match Trend-Parity)
    month = pd.Series(out.index, index=out.index).dt.to_period("M")
    new_month = month.ne(month.shift())
    out = out.where(new_month, np.nan).ffill().fillna(0.0)
    return out


def bt(w, label, start=None):
    start = start or START_DAVEY
    cols = list(w.columns)
    prices = master[cols].loc[start:]
    ww = w.loc[start:]
    r = run_backtest(prices, ww, cost_roundtrip=0.001)
    print(pretty_metrics(r.metrics, label))
    return r


U3 = ["QQQ", "IEF", "GLD"]

print("\n--- Over 2007-01 → 2026-04 (Davey window) ---")
bt(sma_inv_vol_weights(U3, 150, 40, 1.0),   "TP  SMA150 x1.0")
bt(sma_inv_vol_weights(U3, 150, 40, 1.2),   "TP  SMA150 x1.2")
bt(davey_inv_vol_weights(U3, 40, 4, 5, 1.0),"TP  Davey 4/5 x1.0")
bt(davey_inv_vol_weights(U3, 40, 4, 5, 1.2),"TP  Davey 4/5 x1.2")

# Davey sensitivity on TP universe
print("\nDavey (x1,x2) sensitivity on QQQ/IEF/GLD (lev 1.0):")
for x1 in [3, 4, 5, 6, 8, 10, 12]:
    for x2 in [3, 4, 5, 6, 8, 10, 12]:
        w = davey_inv_vol_weights(U3, 40, x1, x2, 1.0)
        cols = list(w.columns)
        prices = master[cols].loc[START_DAVEY:]
        ww = w.loc[START_DAVEY:]
        r = run_backtest(prices, ww, cost_roundtrip=0.001)
        mm = r.metrics
        print(f"  x1={x1:<2} x2={x2:<2}  "
              f"CAGR {mm.cagr*100:5.2f}%  DD {mm.max_dd*100:6.2f}%  "
              f"Sharpe {mm.sharpe:.2f}  Calmar {mm.calmar:.2f}")

# Longer window  1999-2026 for SMA150 comparison (Davey can't go
# earlier than 2007 per the original input)
print("\n--- Over 1999-03 → 2026-04 (SMA150 only) ---")
bt(sma_inv_vol_weights(U3, 150, 40, 1.0),   "TP SMA150 x1.0 (full)",
   start=master.index[0])
bt(sma_inv_vol_weights(U3, 150, 40, 1.2),   "TP SMA150 x1.2 (full)",
   start=master.index[0])
