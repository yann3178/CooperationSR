"""
Iteration 3: momentum-rotation between uncorrelated assets + vol-targeted
total exposure + soft drawdown scaling (no hard stops).
"""
import numpy as np
import pandas as pd

from framework import (
    load_close, build_qld_full, build_tqqq_full, run_backtest,
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
tqqq_full = build_tqqq_full(qqq, load_close("TQQQ"))


def splice(real, synth):
    real = real.dropna()
    cut = real.index[0]
    pre = synth.loc[:cut].iloc[:-1]
    real_scaled = real / real.iloc[0] * synth.loc[cut]
    return pd.concat([pre, real_scaled]).sort_index()


def tlt_syn(ytm, duration=17.0):
    y = ytm.reindex(qqq.index).ffill().bfill() / 100.0
    dy = y.diff().fillna(0.0)
    daily_r = y / TRADING_DAYS - duration * dy
    return (1 + daily_r).cumprod()


def bil_syn():
    y = irx.reindex(qqq.index).ffill().bfill() / 100.0
    return (1 + y / TRADING_DAYS).cumprod()


tlt_full = splice(tlt, tlt_syn(tnx)).reindex(qqq.index).ffill()
ief_full = splice(ief, tlt_syn(tnx, 7.0)).reindex(qqq.index).ffill()
bil_full = splice(bil, bil_syn()).reindex(qqq.index).ffill()

# Gold: don't extrapolate pre-2004; substitute BIL before inception
gld_ext = gld.reindex(qqq.index)
gld_ext.loc[:gld.index[0]] = bil_full.loc[:gld.index[0]] / bil_full.loc[gld.index[0]] * gld.iloc[0]
gld_ext = gld_ext.ffill()

master = pd.DataFrame(
    {
        "QQQ": qqq,
        "QLD": qld_full.reindex(qqq.index),
        "TQQQ": tqqq_full.reindex(qqq.index),
        "IEF": ief_full,
        "TLT": tlt_full,
        "BIL": bil_full,
        "GLD": gld_ext,
    }
).dropna(subset=["QQQ"]).ffill()


# -------------------- STRATEGY F --------------------
# Keller-style momentum rotation with defensive canary
# Universe = [QLD, TLT, GLD]  (risk-on)
# Canary   = QQQ > SMA200  AND 13612W momentum > 0
# If canary fails -> 100% BIL
# Monthly rebalance.
# -------------------------------------------------------
def keller_rotation(universe, canary_mom_series, defensive="BIL",
                    top_n=1, lookback=126, rebal="M"):
    """Pick top-N by `lookback`-day return, or defensive if canary negative."""
    prices = master[universe + [defensive]]
    rets_l = prices[universe].pct_change(lookback)

    idx = prices.index
    w = pd.DataFrame(0.0, index=idx, columns=prices.columns)
    rebal_mask = pd.Series(idx, index=idx).dt.to_period("M").ne(
        pd.Series(idx, index=idx).dt.to_period("M").shift()
    )
    canary_ok = canary_mom_series.reindex(idx).fillna(False)

    for d in idx[rebal_mask]:
        if not canary_ok.loc[d]:
            w.loc[d, defensive] = 1.0
            continue
        r = rets_l.loc[d]
        top = r.nlargest(top_n).index
        # Only take assets with positive momentum
        top = [t for t in top if r.loc[t] > 0]
        if not top:
            w.loc[d, defensive] = 1.0
            continue
        for t in top:
            w.loc[d, t] = 1.0 / len(top)

    w = w.where(rebal_mask, np.nan).ffill().fillna(0.0)
    # shift by 1 so weights take effect next day
    w = w.shift(1).fillna(0.0)
    return prices, w


px = master["QQQ"]
mom_ok = (px > sma(px, 200)) & (px > sma(px, 50))

print("\n=== Strategy F: Keller rotation QLD/TLT/GLD w/ canary ===")
prices, w = keller_rotation(["QLD", "TLT", "GLD"], mom_ok, "BIL",
                            top_n=1, lookback=126)
res = run_backtest(prices, w)
print(pretty_metrics(res.metrics, "F / top1 126d"))

# Various lookbacks
for lb in [63, 84, 126, 189, 252]:
    prices, w = keller_rotation(["QLD", "TLT", "GLD"], mom_ok, "BIL", 1, lb)
    res = run_backtest(prices, w)
    print(pretty_metrics(res.metrics, f"F top1 lb={lb}"))

# Top-2 equally weighted
print()
for lb in [63, 84, 126, 189, 252]:
    prices, w = keller_rotation(["QLD","TLT","GLD"], mom_ok, "BIL", 2, lb)
    res = run_backtest(prices, w)
    print(pretty_metrics(res.metrics, f"F top2 lb={lb}"))

# -------------------- STRATEGY G --------------------
# Accelerating momentum (1+3+6+12 month avg) across wider universe
# --------------------------------------------------------
print("\n=== Strategy G: accelerating momentum ===")
def accel_mom(prices, lookbacks=(21, 63, 126, 252)):
    rets = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for lb in lookbacks:
        rets = rets + prices.pct_change(lb) / len(lookbacks)
    return rets

def rotate_accel(universe, canary_ok, defensive="BIL", top_n=1,
                 lookbacks=(21, 63, 126, 252)):
    prices = master[universe + [defensive]]
    scores = accel_mom(prices[universe], lookbacks)
    idx = prices.index
    w = pd.DataFrame(0.0, index=idx, columns=prices.columns)
    rebal_mask = pd.Series(idx, index=idx).dt.to_period("M").ne(
        pd.Series(idx, index=idx).dt.to_period("M").shift()
    )
    ok = canary_ok.reindex(idx).fillna(False)
    for d in idx[rebal_mask]:
        if not ok.loc[d]:
            w.loc[d, defensive] = 1.0
            continue
        s = scores.loc[d]
        top = s.nlargest(top_n).index
        top = [t for t in top if s.loc[t] > 0]
        if not top:
            w.loc[d, defensive] = 1.0
            continue
        for t in top:
            w.loc[d, t] = 1.0 / len(top)
    w = w.where(rebal_mask, np.nan).ffill().fillna(0.0).shift(1).fillna(0.0)
    return prices, w

for uni, top in [
    (["QLD","TLT","GLD"], 1),
    (["QLD","TLT","GLD"], 2),
    (["QLD","TLT","GLD","IEF"], 1),
    (["QLD","TLT","GLD","IEF"], 2),
    (["QQQ","TLT","GLD","IEF"], 2),
    (["QLD","IEF","GLD"], 2),
    (["QLD","IEF","GLD"], 1),
    (["TQQQ","TLT","GLD"], 1),
    (["TQQQ","IEF","GLD"], 1),
]:
    prices, w = rotate_accel(uni, mom_ok, "BIL", top_n=top)
    res = run_backtest(prices, w)
    print(pretty_metrics(res.metrics, f"{uni} top{top}"))

# -------------------- STRATEGY H --------------------
# Composite allocation: baseline 50% IEF + 30% GLD + 20% {QLD OR BIL}
# with fast trend filter
# --------------------------------------------------------
print("\n=== Strategy H: 50/30/20 core, QLD sleeve timed ===")
for sma_n in [50, 100, 150, 200]:
    bull = (master["QQQ"] > sma(master["QQQ"], sma_n)).shift(1).fillna(False)
    w = pd.DataFrame(0.0, index=master.index,
                     columns=["QLD","IEF","GLD","BIL"])
    w["QLD"] = 0.20 * bull.astype(float)
    w["IEF"] = 0.50
    w["GLD"] = 0.30
    w["BIL"] = 1 - w[["QLD","IEF","GLD"]].sum(axis=1)
    # monthly rebalance
    rebal = pd.Series(w.index, index=w.index).dt.to_period("M").ne(
        pd.Series(w.index, index=w.index).dt.to_period("M").shift()
    )
    w_m = w.where(rebal, np.nan).ffill().fillna(0.0)
    res = run_backtest(master[w.columns], w_m)
    print(pretty_metrics(res.metrics, f"H sma{sma_n}"))

# 30/40/30 variant
print()
for q, i, g in [(0.30, 0.40, 0.30), (0.40, 0.30, 0.30),
                (0.50, 0.30, 0.20), (0.20, 0.60, 0.20)]:
    bull = (master["QQQ"] > sma(master["QQQ"], 150)).shift(1).fillna(False)
    w = pd.DataFrame(0.0, index=master.index,
                     columns=["QLD","IEF","GLD","BIL"])
    w["QLD"] = q * bull.astype(float)
    w["IEF"] = i
    w["GLD"] = g
    w["BIL"] = 1 - w[["QLD","IEF","GLD"]].sum(axis=1)
    rebal = pd.Series(w.index, index=w.index).dt.to_period("M").ne(
        pd.Series(w.index, index=w.index).dt.to_period("M").shift()
    )
    w_m = w.where(rebal, np.nan).ffill().fillna(0.0)
    res = run_backtest(master[w.columns], w_m)
    print(pretty_metrics(res.metrics, f"H {q}/{i}/{g}"))
