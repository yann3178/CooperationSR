"""
Iteration 6: refine Strategy P with a drawdown-aware overlay.

Strategy P base: inverse-vol QQQ/TLT/GLD, each asset gated by SMA150 trend,
monthly rebalance.

Overlay: soft drawdown scaling.  When portfolio is X% below its
40-day rolling high, scale gross exposure by a factor in [0, 1].
"""
import numpy as np
import pandas as pd

from framework import (
    load_close, build_qld_full, run_backtest, compute_metrics,
    pretty_metrics, sma, realised_vol, TRADING_DAYS,
)

qqq = load_close("QQQ")
tlt = load_close("TLT")
ief = load_close("IEF")
bil = load_close("BIL")
gld = load_close("GLD")
tnx = load_close("^TNX")
irx = load_close("^IRX")


def tlt_syn(ytm, duration=17.0):
    y = ytm.reindex(qqq.index).ffill().bfill() / 100.0
    dy = y.diff().fillna(0.0)
    return (1 + y / TRADING_DAYS - duration * dy).cumprod()


def bil_syn():
    y = irx.reindex(qqq.index).ffill().bfill() / 100.0
    return (1 + y / TRADING_DAYS).cumprod()


def splice(real, synth):
    real = real.dropna()
    cut = real.index[0]
    pre = synth.loc[:cut].iloc[:-1]
    real_scaled = real / real.iloc[0] * synth.loc[cut]
    return pd.concat([pre, real_scaled]).sort_index()


tlt_full = splice(tlt, tlt_syn(tnx)).reindex(qqq.index).ffill()
ief_full = splice(ief, tlt_syn(tnx, 7.0)).reindex(qqq.index).ffill()
bil_full = splice(bil, bil_syn()).reindex(qqq.index).ffill()
gld_ext = gld.reindex(qqq.index).ffill().bfill()

qld_full = build_qld_full(qqq, load_close("QLD"))

master = pd.DataFrame({
    "QQQ": qqq,
    "QLD": qld_full.reindex(qqq.index),
    "TLT": tlt_full,
    "IEF": ief_full,
    "GLD": gld_ext,
    "BIL": bil_full,
}).dropna(subset=["QQQ"]).ffill()

rebal_m = pd.Series(master.index, index=master.index).dt.to_period("M").ne(
    pd.Series(master.index, index=master.index).dt.to_period("M").shift()
)
monthly = lambda w: w.where(rebal_m, np.nan).ffill().fillna(0.0)


# ---------------- Build P-style base weights ----------------
def base_weights(universe, sma_n=150, vol_win=40):
    tri = master[universe]
    trend = tri.gt(tri.rolling(sma_n).mean())
    v = tri.pct_change().rolling(vol_win).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / v).fillna(0).where(trend, 0.0)
    tot = inv.sum(axis=1)
    w_iv = inv.div(tot.replace(0, np.nan), axis=0).fillna(0)
    w = pd.DataFrame(0.0, index=master.index, columns=universe + ["BIL"])
    w[universe] = w_iv
    w["BIL"] = 1 - w[universe].sum(axis=1)
    return monthly(w)


# Base + drawdown overlay implemented inside a custom engine
def run_with_dd_overlay(prices, base_w, dd_trigger=0.04, dd_full=0.08,
                        cost=0.001, risk_off_col="BIL"):
    """Simulate the strategy applying a drawdown-aware scaling overlay.

    scale = 1.0 if current DD <= dd_trigger
            linear down to 0 as DD -> dd_full
    Unused gross goes into BIL.
    """
    prices = prices.copy()
    base_w = base_w.reindex(prices.index).fillna(0.0)
    cols = list(prices.columns)
    if risk_off_col not in cols:
        cols = cols + [risk_off_col]

    rets = prices.pct_change().fillna(0.0).values
    n = len(prices)
    k = len(cols)

    w_arr = np.zeros((n, k))
    applied_w = np.zeros_like(w_arr)
    equity = np.ones(n)
    peak = 1.0
    prev = np.zeros(k)
    cost_side = cost / 2.0

    # base_w columns may not match cols
    col_index = {c: i for i, c in enumerate(cols)}
    base_vals = np.zeros((n, k))
    for c in base_w.columns:
        if c in col_index:
            base_vals[:, col_index[c]] = base_w[c].values

    ro_i = col_index[risk_off_col]

    for t in range(n):
        dd = equity[t - 1] / peak - 1.0 if t > 0 else 0.0
        if dd > -dd_trigger:
            scale = 1.0
        elif dd <= -dd_full:
            scale = 0.0
        else:
            scale = (dd + dd_full) / (dd_full - dd_trigger)
            scale = max(0.0, min(1.0, scale))

        cur = base_vals[t].copy()
        # Determine current gross risk (everything except BIL)
        risky_idx = [i for i in range(k) if i != ro_i]
        risky_w = cur.copy()
        risky_w[ro_i] = 0.0
        cur_risky = risky_w * scale
        # Put remainder in BIL
        cur_final = cur_risky.copy()
        cur_final[ro_i] = 1 - cur_risky.sum()

        turnover = np.sum(np.abs(cur_final - prev))
        cost_paid = turnover * cost_side

        if t > 0:
            r = float(np.dot(prev, rets[t]))
            equity[t] = equity[t - 1] * (1 + r - cost_paid)
        else:
            equity[t] = 1.0 - cost_paid

        peak = max(peak, equity[t])
        applied_w[t] = cur_final
        prev = cur_final

    eq_s = pd.Series(equity, index=prices.index)
    pos_df = pd.DataFrame(applied_w, index=prices.index, columns=cols)
    ret_s = eq_s.pct_change().fillna(0.0)
    m = compute_metrics(eq_s, pos_df)
    return eq_s, pos_df, ret_s, m


# ------------------ Experiments ------------------
print("\n=== Base P refresh ===")
for uni, sma_n in [
    (["QQQ","TLT","GLD"], 150),
    (["QQQ","TLT","GLD"], 100),
    (["QLD","TLT","GLD"], 150),
    (["QQQ","TLT","GLD","IEF"], 150),
    (["QQQ","IEF","GLD"], 150),
    (["QLD","IEF","GLD"], 150),
]:
    bw = base_weights(uni, sma_n)
    prices = master[list(bw.columns)]
    res = run_backtest(prices, bw)
    print(pretty_metrics(res.metrics, f"{uni} sma{sma_n}"))

print("\n=== With drawdown overlay ===")
for uni in [["QQQ","TLT","GLD"], ["QLD","TLT","GLD"], ["QQQ","IEF","GLD"]]:
    bw = base_weights(uni, sma_n=150)
    prices = master[list(bw.columns)]
    for trig, fullv in [(0.03, 0.06), (0.04, 0.08), (0.05, 0.10),
                        (0.03, 0.08), (0.02, 0.06)]:
        eq, pos, _, m = run_with_dd_overlay(
            prices, bw, dd_trigger=trig, dd_full=fullv
        )
        print(pretty_metrics(m, f"{uni[:]} trig{trig} full{fullv}"))

# ---------------- Variant: blend P with a safety bond sleeve ----
print("\n=== P-blend: 60% P-style + 40% IEF baseline ===")
bw = base_weights(["QQQ","TLT","GLD"], 150)
# scale risky part 0.6, add fixed 0.4 IEF
bw_scaled = bw.copy()
bw_scaled[["QQQ","TLT","GLD"]] *= 0.6
bw_scaled["BIL"] *= 0.6
bw_scaled["IEF"] = 0.4
prices = master[["QQQ","TLT","GLD","IEF","BIL"]]
res = run_backtest(prices, bw_scaled[prices.columns])
print(pretty_metrics(res.metrics, "P-blend 60/40"))

# Leveraged: 120% P-style (since low vol)
print("\n=== P leveraged to 1.2x ===")
bw = base_weights(["QQQ","TLT","GLD"], 150)
bw_lev = bw.copy()
bw_lev[["QQQ","TLT","GLD"]] *= 1.3
bw_lev["BIL"] = 1 - bw_lev[["QQQ","TLT","GLD"]].sum(axis=1)
prices = master[list(bw_lev.columns)]
res = run_backtest(prices, bw_lev)
print(pretty_metrics(res.metrics, "P lev 1.3x"))

# P with QLD
print("\n=== P variant: swap QQQ for QLD ===")
bw = base_weights(["QLD","TLT","GLD"], 150)
for trig, fullv in [(0.03, 0.06), (0.04, 0.08)]:
    eq, pos, _, m = run_with_dd_overlay(master[list(bw.columns)], bw,
                                        dd_trigger=trig, dd_full=fullv)
    print(pretty_metrics(m, f"QLD-P trig{trig} full{fullv}"))
