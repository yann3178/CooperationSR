"""
Iteration 5: focus on low-vol high-Sharpe building blocks then scale.

The key question: can we find a sleeve with Sharpe > 1.3 that is low-vol
enough that 1.5-2x leverage still keeps DD <= 10%?
"""
import numpy as np
import pandas as pd

from framework import (
    load_close, build_qld_full, run_backtest,
    compute_metrics, pretty_metrics, sma, realised_vol, TRADING_DAYS,
)

qqq = load_close("QQQ")
tlt = load_close("TLT")
ief = load_close("IEF")
bil = load_close("BIL")
gld = load_close("GLD")
vix = load_close("^VIX")
tnx = load_close("^TNX")
irx = load_close("^IRX")

qld_full = build_qld_full(qqq, load_close("QLD"))


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

master = pd.DataFrame({
    "QQQ": qqq,
    "QLD": qld_full.reindex(qqq.index),
    "IEF": ief_full,
    "TLT": tlt_full,
    "BIL": bil_full,
    "GLD": gld_ext,
}).dropna(subset=["QQQ"]).ffill()

rebal_m = pd.Series(master.index, index=master.index).dt.to_period("M").ne(
    pd.Series(master.index, index=master.index).dt.to_period("M").shift()
)


def monthly(w: pd.DataFrame) -> pd.DataFrame:
    return w.where(rebal_m, np.nan).ffill().fillna(0.0)


def test(weights, label, cols=None):
    cols = cols or list(weights.columns)
    w = weights[cols].reindex(master.index).fillna(0.0)
    res = run_backtest(master[cols], w)
    print(pretty_metrics(res.metrics, label))
    return res


# -----------------------------------------------------------------------
# Strategy L : 50/50 QLD/TLT risk parity static
# -----------------------------------------------------------------------
print("\n=== L: Static 50/50 QLD/TLT ===")
w = pd.DataFrame(0.0, index=master.index, columns=["QLD", "TLT"])
w[["QLD", "TLT"]] = 0.5
test(monthly(w), "L 50/50 QLD/TLT")

for q, t in [(0.3, 0.7), (0.4, 0.6), (0.6, 0.4), (0.25, 0.75),
             (0.35, 0.65), (0.45, 0.55)]:
    w = pd.DataFrame(0.0, index=master.index, columns=["QLD", "TLT"])
    w["QLD"] = q
    w["TLT"] = t
    test(monthly(w), f"L {q}/{t}")

# -----------------------------------------------------------------------
# Strategy M : inverse-vol QLD/TLT dynamic (risk parity)
# -----------------------------------------------------------------------
print("\n=== M: Inverse-vol QLD/TLT (monthly) ===")
for win in [20, 40, 60]:
    v = master[["QLD", "TLT"]].pct_change().rolling(win).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / v).fillna(0)
    w_iv = inv.div(inv.sum(axis=1), axis=0).fillna(0)
    w = pd.DataFrame(0.0, index=master.index, columns=["QLD", "TLT"])
    w[["QLD", "TLT"]] = w_iv
    test(monthly(w), f"M inv-vol win={win}")

# -----------------------------------------------------------------------
# Strategy N : inverse-vol QLD/TLT/GLD triple
# -----------------------------------------------------------------------
print("\n=== N: Inverse-vol triple (QLD/TLT/GLD) ===")
for win in [20, 40, 60]:
    tri = master[["QLD", "TLT", "GLD"]]
    v = tri.pct_change().rolling(win).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / v).fillna(0)
    w_iv = inv.div(inv.sum(axis=1), axis=0).fillna(0)
    w = pd.DataFrame(0.0, index=master.index, columns=["QLD", "TLT", "GLD"])
    w[["QLD","TLT","GLD"]] = w_iv
    test(monthly(w), f"N inv-vol win={win}")


# -----------------------------------------------------------------------
# Strategy O : trend-gated inverse-vol QLD/TLT/GLD
# Each asset ON only if above its SMA200.
# -----------------------------------------------------------------------
print("\n=== O: Inverse-vol QLD/TLT/GLD, trend-gated per asset ===")
for sma_n in [100, 150, 200]:
    tri = master[["QLD", "TLT", "GLD"]]
    trend = tri.gt(tri.rolling(sma_n).mean())
    v = tri.pct_change().rolling(40).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / v).fillna(0)
    inv = inv.where(trend, 0.0)
    tot = inv.sum(axis=1)
    w_iv = inv.div(tot.replace(0, np.nan), axis=0).fillna(0)
    # Remainder = BIL
    w = pd.DataFrame(0.0, index=master.index,
                     columns=["QLD", "TLT", "GLD", "BIL"])
    w[["QLD","TLT","GLD"]] = w_iv
    w["BIL"] = 1 - w.sum(axis=1)
    test(monthly(w), f"O gate={sma_n}")

# -----------------------------------------------------------------------
# Strategy P : trend-gated inverse-vol on QQQ (not leveraged) + TLT + GLD
# -----------------------------------------------------------------------
print("\n=== P: QQQ/TLT/GLD trend-gated inv-vol ===")
for sma_n in [100, 150, 200]:
    tri = master[["QQQ", "TLT", "GLD"]]
    trend = tri.gt(tri.rolling(sma_n).mean())
    v = tri.pct_change().rolling(40).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / v).fillna(0).where(trend, 0.0)
    tot = inv.sum(axis=1)
    w_iv = inv.div(tot.replace(0, np.nan), axis=0).fillna(0)
    w = pd.DataFrame(0.0, index=master.index,
                     columns=["QQQ","TLT","GLD","BIL"])
    w[["QQQ","TLT","GLD"]] = w_iv
    w["BIL"] = 1 - w.sum(axis=1)
    test(monthly(w), f"P gate={sma_n}")

# -----------------------------------------------------------------------
# Strategy Q : portfolio-level vol-target layer on top of strat O
# -----------------------------------------------------------------------
print("\n=== Q: O with portfolio vol target ===")
def vol_target_overlay(prices, weights, target_vol=0.08, lookback=40,
                       max_leverage=2.0, cost=0.001):
    rets = prices.pct_change().fillna(0.0)
    # daily portfolio gross return with base weights
    port_ret = (weights.shift(1) * rets).sum(axis=1)
    port_vol = port_ret.rolling(lookback).std() * np.sqrt(TRADING_DAYS)
    scale = (target_vol / port_vol).clip(upper=max_leverage).fillna(0)
    return weights.mul(scale, axis=0)

tri = master[["QLD", "TLT", "GLD"]]
trend = tri.gt(tri.rolling(200).mean())
v = tri.pct_change().rolling(40).std() * np.sqrt(TRADING_DAYS)
inv = (1 / v).fillna(0).where(trend, 0.0)
tot = inv.sum(axis=1)
w_iv = inv.div(tot.replace(0, np.nan), axis=0).fillna(0)
w_base = pd.DataFrame(0.0, index=master.index,
                      columns=["QLD","TLT","GLD","BIL"])
w_base[["QLD","TLT","GLD"]] = w_iv
w_base["BIL"] = 1 - w_base.sum(axis=1)
w_base = monthly(w_base)

for tv in [0.06, 0.07, 0.08, 0.09, 0.10]:
    w_ovr = vol_target_overlay(master[w_base.columns], w_base,
                               target_vol=tv, max_leverage=2.0)
    w_ovr["BIL"] = (1 - w_ovr[["QLD","TLT","GLD"]].sum(axis=1)).clip(lower=-1, upper=1)
    test(monthly(w_ovr), f"Q target={tv*100:.0f}%")


# -----------------------------------------------------------------------
# Strategy R : Ensemble of sub-strategies
# -----------------------------------------------------------------------
print("\n=== R: Ensemble ===")
def subA():  # simple QQQ SMA200
    bull = (master["QQQ"] > sma(master["QQQ"], 200)).shift(1).fillna(False).astype(bool)
    w = pd.DataFrame(0.0, index=master.index, columns=["QLD","IEF","BIL"])
    w["QLD"] = bull.astype(float) * 0.5
    w["IEF"] = 0.3
    w["BIL"] = 1 - w["QLD"] - w["IEF"]
    return monthly(w)

def subB():  # inverse vol QLD+TLT
    tri = master[["QLD","TLT"]]
    v = tri.pct_change().rolling(40).std() * np.sqrt(TRADING_DAYS)
    inv = (1/v).fillna(0)
    w_iv = inv.div(inv.sum(axis=1), axis=0).fillna(0)
    w = pd.DataFrame(0.0, index=master.index, columns=["QLD","IEF","TLT","BIL"])
    w[["QLD","TLT"]] = w_iv
    return monthly(w)

def subC():  # gated triple
    tri = master[["QLD", "TLT", "GLD"]]
    trend = tri.gt(tri.rolling(200).mean())
    v = tri.pct_change().rolling(40).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / v).fillna(0).where(trend, 0.0)
    tot = inv.sum(axis=1)
    w_iv = inv.div(tot.replace(0, np.nan), axis=0).fillna(0)
    w = pd.DataFrame(0.0, index=master.index,
                     columns=["QLD", "TLT", "GLD", "BIL"])
    w[["QLD","TLT","GLD"]] = w_iv
    w["BIL"] = 1 - w.sum(axis=1)
    return monthly(w)

cols_all = ["QLD","TLT","GLD","IEF","BIL"]
wA = subA().reindex(columns=cols_all).fillna(0)
wB = subB().reindex(columns=cols_all).fillna(0)
wC = subC().reindex(columns=cols_all).fillna(0)

wE = (wA + wB + wC) / 3
test(wE, "R ensemble A+B+C")

# Ensemble + vol target
wE2 = vol_target_overlay(master[cols_all], wE, target_vol=0.08)
# re-normalise to keep BIL as cash buffer
wE2["BIL"] = (1 - wE2[["QLD","TLT","GLD","IEF"]].sum(axis=1)).clip(-1, 1)
test(monthly(wE2), "R ensemble + vt 8%")
