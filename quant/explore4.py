"""
Iteration 4: explicitly use SHORT exposure during bearish regimes.
The math: a perfect regime indicator that switches between +QLD and -QQQ
should turn every drawdown into a profit. Imperfect signals will still
strongly reduce MaxDD.
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

# Synthetic PSQ (short QQQ 1x)
def inv_qqq():
    r = qqq.pct_change().fillna(0.0)
    # Short position daily return = -r - financing cost
    daily_cost = (0.0095 + 0.003) / TRADING_DAYS
    r_short = -r - daily_cost
    s = (1 + r_short).cumprod() * 100
    return s

psq_full = inv_qqq()

gld_ext = gld.reindex(qqq.index)
gld_ext.loc[:gld.index[0]] = bil_full.loc[:gld.index[0]] / bil_full.loc[gld.index[0]] * gld.iloc[0]
gld_ext = gld_ext.ffill()

master = pd.DataFrame({
    "QQQ": qqq,
    "QLD": qld_full.reindex(qqq.index),
    "PSQ": psq_full,
    "IEF": ief_full,
    "TLT": tlt_full,
    "BIL": bil_full,
    "GLD": gld_ext,
}).dropna(subset=["QQQ"]).ffill()

print(f"master: {master.index[0].date()} -> {master.index[-1].date()} "
      f"({len(master)} rows)")
print("PSQ sanity (buy & hold):")
m = compute_metrics(master["PSQ"] / master["PSQ"].iloc[0])
print(pretty_metrics(m, "PSQ synthetic"))


px = master["QQQ"]


def regime(px, sma_n=200, mom_n=63, vol_n=20, vol_max=0.40):
    """Robust bull regime: trend + positive momentum + not-too-high vol."""
    trend = px > sma(px, sma_n)
    mom = (px / px.shift(mom_n) - 1) > 0
    vol = realised_vol(px, vol_n)
    vol_ok = vol < vol_max
    return (trend & mom & vol_ok)


def run_named(weights, label, cols=None):
    cols = cols or list(weights.columns)
    w = weights[cols].reindex(master.index).fillna(0.0)
    res = run_backtest(master[cols], w)
    print(pretty_metrics(res.metrics, label))
    return res


# -----------------------------------------------------------------------
# Strategy I: bull = (QLD + IEF), bear = (IEF + PSQ). Hedged reversal.
# -----------------------------------------------------------------------
print("\n=== Strategy I: hedged reversal (QLD+IEF / IEF+PSQ) ===")
for sma_n in [100, 150, 200]:
    for qld_w, ief_bull, psq_w, ief_bear in [
        (0.60, 0.40, 0.40, 0.60),
        (0.50, 0.50, 0.30, 0.70),
        (0.70, 0.30, 0.30, 0.70),
        (0.50, 0.50, 0.50, 0.50),
    ]:
        bull_np = regime(px, sma_n=sma_n).shift(1).fillna(False).astype(bool).values
        w = pd.DataFrame(0.0, index=master.index, columns=["QLD","IEF","PSQ"])
        w.loc[master.index[bull_np], "QLD"] = qld_w
        w.loc[master.index[bull_np], "IEF"] = ief_bull
        w.loc[master.index[~bull_np], "PSQ"] = psq_w
        w.loc[master.index[~bull_np], "IEF"] = ief_bear
        rebal = pd.Series(w.index, index=w.index).dt.to_period("M").ne(
            pd.Series(w.index, index=w.index).dt.to_period("M").shift()
        )
        w_m = w.where(rebal, np.nan).ffill().fillna(0.0)
        res = run_backtest(master[["QLD","IEF","PSQ"]], w_m)
        print(pretty_metrics(res.metrics,
              f"I sma{sma_n} {qld_w}/{ief_bull} | {psq_w}/{ief_bear}"))

# -----------------------------------------------------------------------
# Strategy J: triple sleeve — QLD + GLD + TLT, gated by regime
# -----------------------------------------------------------------------
print("\n=== Strategy J: triple sleeve (QLD+GLD+TLT / BIL+PSQ+GLD) ===")
for sma_n in [100, 150, 200]:
    b = regime(px, sma_n=sma_n).shift(1).fillna(False).astype(bool).values
    w = pd.DataFrame(0.0, index=master.index,
                     columns=["QLD","GLD","TLT","BIL","PSQ","IEF"])
    w.loc[master.index[b], "QLD"] = 0.40
    w.loc[master.index[b], "GLD"] = 0.20
    w.loc[master.index[b], "TLT"] = 0.40
    w.loc[master.index[~b], "PSQ"] = 0.30
    w.loc[master.index[~b], "GLD"] = 0.20
    w.loc[master.index[~b], "IEF"] = 0.50
    rebal = pd.Series(w.index, index=w.index).dt.to_period("M").ne(
        pd.Series(w.index, index=w.index).dt.to_period("M").shift()
    )
    w_m = w.where(rebal, np.nan).ffill().fillna(0.0)
    res = run_backtest(master[w.columns], w_m)
    print(pretty_metrics(res.metrics, f"J sma{sma_n}"))

# -----------------------------------------------------------------------
# Strategy K: Pure equity hedged  — always long QLD w/ dynamic hedge
# -----------------------------------------------------------------------
# Always hold 0.5 QLD.  Size short hedge PSQ based on regime.
# Bull: 0 hedge.  Bear: hedge up to 1.0 PSQ.
# -----------------------------------------------------------------------
print("\n=== Strategy K: always-long QLD + dynamic PSQ hedge ===")
for qld_w in [0.4, 0.5, 0.6]:
    for hedge_max in [0.5, 0.75, 1.0, 1.25]:
        b = regime(px).shift(1).fillna(False).astype(bool).values
        w = pd.DataFrame(0.0, index=master.index,
                         columns=["QLD","PSQ","IEF","BIL"])
        w["QLD"] = qld_w
        w.loc[master.index[~b], "PSQ"] = hedge_max
        w["IEF"] = (1 - w["QLD"] - w["PSQ"]).clip(lower=0)
        rebal = pd.Series(w.index, index=w.index).dt.to_period("M").ne(
            pd.Series(w.index, index=w.index).dt.to_period("M").shift()
        )
        w_m = w.where(rebal, np.nan).ffill().fillna(0.0)
        res = run_backtest(master[w.columns], w_m)
        print(pretty_metrics(res.metrics,
              f"K qld{qld_w} hedge{hedge_max}"))
