"""
Final head-to-head: Davey monthly breakout gate vs SMA150 gate vs
blended gate, over the full 1999-03 → 2026-04 window.

Removes the Davey start-date filter so the two gates are compared on
the same 27-year window.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from framework import (
    load_close, run_backtest, compute_metrics, pretty_metrics, TRADING_DAYS,
)
from strategy import load_universe as load_tp_universe

master = load_tp_universe()
U = ["QQQ", "IEF", "GLD"]
CASH = "BIL"


def davey_signal_nofilter(prices, x1, x2):
    """Davey monthly breakout, no start-date filter."""
    m = prices.resample("ME").last()
    n, k = m.shape
    inm = np.zeros((n, k))
    for i in range(max(x1, x2), n):
        for j in range(k):
            prev = inm[i - 1, j] if i > 0 else 0
            c0, c1, c2 = m.iloc[i, j], m.iloc[i - x1, j], m.iloc[i - x2, j]
            if prev == 0:
                inm[i, j] = 1.0 if c0 - c1 >= 0 else 0.0
            else:
                inm[i, j] = 0.0 if c0 - c2 < 0 else 1.0
    mp = pd.DataFrame(inm, index=m.index, columns=m.columns)
    mp = mp.shift(1).fillna(0.0)
    return mp.reindex(prices.index).ffill().fillna(0.0)


def sma_signal(prices, sma_n=150):
    return prices.gt(prices.rolling(sma_n).mean()).astype(float)


def inv_vol_weights_from_signal(prices, sig, vol_win=40, leverage=1.0,
                                monthly_rebal=True):
    vol = prices.pct_change().rolling(vol_win).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / vol).where(sig > 0, 0.0).fillna(0.0)
    tot = inv.sum(axis=1)
    w = inv.div(tot.replace(0, np.nan), axis=0).fillna(0.0) * leverage
    out = pd.DataFrame(0.0, index=master.index, columns=list(prices.columns)+[CASH])
    out[list(prices.columns)] = w
    out[CASH] = 1.0 - out[list(prices.columns)].sum(axis=1)
    if monthly_rebal:
        month = pd.Series(out.index, index=out.index).dt.to_period("M")
        new_month = month.ne(month.shift())
        out = out.where(new_month, np.nan).ffill().fillna(0.0)
    return out


def bt(w, label):
    cols = list(w.columns)
    res = run_backtest(master[cols], w, cost_roundtrip=0.001)
    print(pretty_metrics(res.metrics, label))
    return res


print("Baselines")
print("=" * 80)
qqq_m = compute_metrics(master["QQQ"] / master["QQQ"].iloc[0])
print(pretty_metrics(qqq_m, "QQQ B&H 1999-2026"))

print("\n--- Full history 1999-03 → 2026-04 ---")

# SMA150 base
sig = sma_signal(master[U], 150)
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.0), "SMA150 lev1.0")
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.2), "SMA150 lev1.2")

# Davey x1=4, x2=5 (original)
sig = davey_signal_nofilter(master[U], 4, 5)
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.0), "Davey 4/5 lev1.0")
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.2), "Davey 4/5 lev1.2")

# Davey x1=8, x2=3 (best from grid on 2007-2026)
sig = davey_signal_nofilter(master[U], 8, 3)
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.0), "Davey 8/3 lev1.0")
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.2), "Davey 8/3 lev1.2")

# Davey x1=8, x2=8
sig = davey_signal_nofilter(master[U], 8, 8)
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.0), "Davey 8/8 lev1.0")
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.2), "Davey 8/8 lev1.2")

# Davey x1=8, x2=12
sig = davey_signal_nofilter(master[U], 8, 12)
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.0), "Davey 8/12 lev1.0")
bt(inv_vol_weights_from_signal(master[U], sig, 40, 1.2), "Davey 8/12 lev1.2")

# Combined: SMA150 AND Davey 8/8 (asset must pass BOTH)
print("\n--- Combined gates (AND) ---")
sma150 = sma_signal(master[U], 150)
d88 = davey_signal_nofilter(master[U], 8, 8)
combined = ((sma150 > 0) & (d88 > 0)).astype(float)
bt(inv_vol_weights_from_signal(master[U], combined, 40, 1.0), "SMA150 AND Dav88 lev1.0")
bt(inv_vol_weights_from_signal(master[U], combined, 40, 1.2), "SMA150 AND Dav88 lev1.2")
bt(inv_vol_weights_from_signal(master[U], combined, 40, 1.4), "SMA150 AND Dav88 lev1.4")

# Combined: OR gate
combined_or = ((sma150 > 0) | (d88 > 0)).astype(float)
bt(inv_vol_weights_from_signal(master[U], combined_or, 40, 1.0), "SMA150 OR Dav88 lev1.0")
bt(inv_vol_weights_from_signal(master[U], combined_or, 40, 1.2), "SMA150 OR Dav88 lev1.2")

# Same for 8/3
d83 = davey_signal_nofilter(master[U], 8, 3)
combined2 = ((sma150 > 0) & (d83 > 0)).astype(float)
bt(inv_vol_weights_from_signal(master[U], combined2, 40, 1.0), "SMA150 AND Dav83 lev1.0")
bt(inv_vol_weights_from_signal(master[U], combined2, 40, 1.2), "SMA150 AND Dav83 lev1.2")
bt(inv_vol_weights_from_signal(master[U], combined2, 40, 1.4), "SMA150 AND Dav83 lev1.4")

# Widest grid: find the best single-gate config over full history
print("\n--- Single Davey gate grid on QQQ/IEF/GLD, full history, lev 1.0 ---")
best = None
for x1 in [3, 4, 5, 6, 8, 10, 12]:
    for x2 in [3, 4, 5, 6, 8, 10, 12]:
        sig = davey_signal_nofilter(master[U], x1, x2)
        w = inv_vol_weights_from_signal(master[U], sig, 40, 1.0)
        res = run_backtest(master[w.columns], w, 0.001)
        m = res.metrics
        print(f"  x1={x1:<2} x2={x2:<2}  CAGR {m.cagr*100:5.2f}%  "
              f"DD {m.max_dd*100:6.2f}%  Sharpe {m.sharpe:.2f}  "
              f"Calmar {m.calmar:.2f}")
        if best is None or m.calmar > best[0]:
            best = (m.calmar, x1, x2, m)
print(f"\nBest Calmar: x1={best[1]} x2={best[2]} → "
      f"{pretty_metrics(best[3], 'Best Davey')}")
