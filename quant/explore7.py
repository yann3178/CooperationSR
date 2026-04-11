"""
Iteration 7: implement published high-Calmar strategies.

- Keller's BAA (Bold Asset Allocation) — reported 15% CAGR / 11% DD since 1970s
- Keller's HAA (Hybrid Asset Allocation) — reported 10% CAGR / 9% DD
- Meb Faber GTAA — aggregating 10-month SMA signals

Use our own ETF translations and see how they score over 2000-2026.
13612W momentum: avg of 1m + 3m + 6m + 12m total-return.
"""
import numpy as np
import pandas as pd

from framework import (
    load_close, build_qld_full, run_backtest, compute_metrics,
    pretty_metrics, sma, TRADING_DAYS,
)

# Data
qqq = load_close("QQQ")
spy = load_close("SPY")
iwm = load_close("IWM")
efa = load_close("EFA")
tlt = load_close("TLT")
ief = load_close("IEF")
shy = load_close("SHY")
gld = load_close("GLD")
dbc = load_close("DBC")
bil = load_close("BIL")
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


# Extended series, all aligned to QQQ index
idx = qqq.index
def extend(real, synth=None):
    if synth is None:
        return real.reindex(idx).ffill().bfill()
    return splice(real, synth).reindex(idx).ffill().bfill()


tlt_full = extend(tlt, tlt_syn(tnx, 17))
ief_full = extend(ief, tlt_syn(tnx, 7))
shy_full = extend(shy, tlt_syn(tnx, 2))
bil_full = extend(bil, bil_syn())

# Extend SPY, IWM, EFA, DBC, GLD by ffill/bfill where missing
spy_full = spy.reindex(idx).ffill()
# SPY starts 1993, QQQ starts 1999, so no hole
efa_full = efa.reindex(idx).ffill().bfill()
iwm_full = iwm.reindex(idx).ffill().bfill()
gld_full = gld.reindex(idx).ffill().bfill()
dbc_full = dbc.reindex(idx).ffill().bfill()

master = pd.DataFrame({
    "QQQ": qqq,
    "QLD": qld_full.reindex(idx),
    "SPY": spy_full,
    "EFA": efa_full,
    "IWM": iwm_full,
    "TLT": tlt_full,
    "IEF": ief_full,
    "SHY": shy_full,
    "GLD": gld_full,
    "DBC": dbc_full,
    "BIL": bil_full,
}).ffill().dropna(subset=["QQQ"])


def mom_13612(series: pd.Series) -> pd.Series:
    r1 = series.pct_change(21)
    r3 = series.pct_change(63)
    r6 = series.pct_change(126)
    r12 = series.pct_change(252)
    return (12 * r1 + 4 * r3 + 2 * r6 + r12) / 19 * 19
    # Keller's original formula: (12*r1 + 4*r3 + 2*r6 + r12)
    # The exact scale doesn't matter for ranking / sign tests.


def mom_sma(series, n=12 * 21):
    """Simple 12-month SMA price divergence."""
    return series / series.rolling(n).mean() - 1


def m13(series):
    return (series / series.shift(21) - 1) * 12 + \
           (series / series.shift(63) - 1) * 4 + \
           (series / series.shift(126) - 1) * 2 + \
           (series / series.shift(252) - 1)


# Monthly rebal mask — use end-of-month
def eom_mask(idx):
    m = pd.Series(idx, index=idx).dt.to_period("M")
    return m.ne(m.shift(-1))

eom = eom_mask(master.index).values  # True at last trading day of each month


def build_weights(universe_off, universe_def, canary, n_off=1, n_def=3,
                  mom_fn=m13):
    """Monthly end-of-month rebalance, execute next day."""
    idx = master.index
    offp = master[universe_off]
    defp = master[universe_def]
    canaryp = master[canary]

    off_score = pd.concat(
        [mom_fn(offp[c]) for c in universe_off], axis=1
    )
    off_score.columns = universe_off
    def_score = pd.concat(
        [mom_fn(defp[c]) for c in universe_def], axis=1
    )
    def_score.columns = universe_def
    can_score = pd.concat(
        [mom_fn(canaryp[c]) for c in canary], axis=1
    )
    can_score.columns = canary

    all_cols = sorted(set(universe_off + universe_def + canary))
    w = pd.DataFrame(0.0, index=idx, columns=all_cols)

    for i in range(len(idx)):
        if not eom[i]:
            continue
        d = idx[i]
        # Canary OK iff all canary momenta > 0
        ok = (can_score.loc[d] > 0).all()
        if ok:
            s = off_score.loc[d]
            top = s.nlargest(n_off).index.tolist()
            top = [t for t in top if s[t] > 0]
            if not top:
                # fall to defensive
                s_def = def_score.loc[d]
                top_def = s_def.nlargest(n_def).index.tolist()
                top_def = [t for t in top_def if s_def[t] > 0]
                if not top_def:
                    # All defensive negative -> cash
                    w.loc[d, "BIL" if "BIL" in all_cols else "SHY"] = 1.0
                else:
                    for t in top_def:
                        w.loc[d, t] = 1.0 / len(top_def)
            else:
                for t in top:
                    w.loc[d, t] = 1.0 / len(top)
        else:
            s_def = def_score.loc[d]
            top_def = s_def.nlargest(n_def).index.tolist()
            top_def = [t for t in top_def if s_def[t] > 0]
            if not top_def:
                w.loc[d, "BIL" if "BIL" in all_cols else "SHY"] = 1.0
            else:
                for t in top_def:
                    w.loc[d, t] = 1.0 / len(top_def)
    # Forward fill + shift by 1 so trades take effect next day
    w_eom = w.replace(0.0, np.nan)
    w_ff = w.where(pd.Series(eom, index=idx), np.nan).ffill().fillna(0.0)
    return w_ff.shift(1).fillna(0.0)


def run(w, label):
    cols = list(w.columns)
    res = run_backtest(master[cols], w)
    print(pretty_metrics(res.metrics, label))
    return res


# -----------------------------------------------------------------------
# 1. Keller BAA-G12 (aggressive, top-1)
# Offensive:  QQQ, SPY, EFA, BND-proxy (use IEF for bonds)
# Defensive:  BIL, IEF, TLT, LQD (we use BIL, IEF, TLT)
# Canary: SPY, TLT
# -----------------------------------------------------------------------
print("\n=== BAA-G12 top-1 aggressive ===")
w = build_weights(
    universe_off=["QQQ","SPY","EFA","IEF"],
    universe_def=["BIL","IEF","TLT"],
    canary=["SPY","TLT"],
    n_off=1, n_def=3, mom_fn=m13,
)
run(w, "BAA-G12 top1")

# Variant with QLD to juice returns
print("\n=== BAA variant with QLD ===")
w = build_weights(
    universe_off=["QLD","SPY","EFA","IEF"],
    universe_def=["BIL","IEF","TLT"],
    canary=["SPY","TLT"],
    n_off=1, n_def=3, mom_fn=m13,
)
run(w, "BAA QLD top1")

# -----------------------------------------------------------------------
# 2. HAA balanced
# Offensive: SPY, IWM, EFA, IEF, TLT, GLD, DBC, ... (choose 4)
# Defensive: IEF, BIL
# Canary: TIP (use IEF as proxy — wasn't in our data)
# We use: canary = SPY AND IEF both positive mom
# -----------------------------------------------------------------------
print("\n=== HAA top-4 offensive ===")
w = build_weights(
    universe_off=["SPY","IWM","EFA","IEF","TLT","GLD","DBC"],
    universe_def=["BIL","IEF"],
    canary=["SPY","IEF"],
    n_off=4, n_def=2, mom_fn=m13,
)
run(w, "HAA top4")

print("\n=== HAA with QLD ===")
w = build_weights(
    universe_off=["QLD","IWM","EFA","IEF","TLT","GLD","DBC"],
    universe_def=["BIL","IEF"],
    canary=["SPY","IEF"],
    n_off=4, n_def=2, mom_fn=m13,
)
run(w, "HAA QLD top4")

print("\n=== HAA top-2 aggressive ===")
w = build_weights(
    universe_off=["QLD","IWM","EFA","IEF","TLT","GLD","DBC"],
    universe_def=["BIL","IEF"],
    canary=["SPY","IEF"],
    n_off=2, n_def=2, mom_fn=m13,
)
run(w, "HAA QLD top2")

print("\n=== HAA top-1 aggressive ===")
w = build_weights(
    universe_off=["QLD","IWM","EFA","IEF","TLT","GLD","DBC"],
    universe_def=["BIL","IEF"],
    canary=["SPY","IEF"],
    n_off=1, n_def=2, mom_fn=m13,
)
run(w, "HAA QLD top1")

# -----------------------------------------------------------------------
# 3. Meb Faber GTAA 5 (equal weighted, each SMA10m gated)
# 20% each: SPY, EFA, AGG (IEF), REIT (no proxy) -> use GLD, DBC
# each held iff price > SMA(10-month); otherwise BIL
# -----------------------------------------------------------------------
print("\n=== Faber GTAA 5 ===")
gtaa_universe = ["SPY", "EFA", "IEF", "GLD", "DBC"]
sma200 = master[gtaa_universe].rolling(200).mean()
above = master[gtaa_universe].gt(sma200)
w = pd.DataFrame(0.0, index=master.index,
                 columns=gtaa_universe + ["BIL"])
for c in gtaa_universe:
    w[c] = above[c].astype(float) * 0.2
w["BIL"] = 1 - w[gtaa_universe].sum(axis=1)
# Monthly rebalance
w = w.where(pd.Series(eom, index=master.index), np.nan).ffill().fillna(0.0)
w = w.shift(1).fillna(0.0)
run(w, "Faber GTAA5")

# GTAA with QLD to substitute SPY
print("\n=== Faber-like with QLD ===")
uni = ["QLD", "EFA", "IEF", "GLD", "DBC"]
sma200 = master[uni].rolling(200).mean()
above = master[uni].gt(sma200)
w = pd.DataFrame(0.0, index=master.index, columns=uni + ["BIL"])
for c in uni:
    w[c] = above[c].astype(float) * 0.2
w["BIL"] = 1 - w[uni].sum(axis=1)
w = w.where(pd.Series(eom, index=master.index), np.nan).ffill().fillna(0.0)
w = w.shift(1).fillna(0.0)
run(w, "Faber-QLD")

# GTAA concentrated: all into the momentum-winning asset
print("\n=== Faber concentrated (top 1 w/ SMA filter) ===")
uni = ["QLD", "TLT", "GLD", "IEF"]
w = build_weights(
    universe_off=uni,
    universe_def=["BIL","IEF"],
    canary=["SPY","IEF"],
    n_off=1, n_def=1, mom_fn=m13,
)
run(w, "top1 QLD/TLT/GLD/IEF")

print("\n=== top-2 QLD/TLT/GLD/IEF ===")
w = build_weights(
    universe_off=uni,
    universe_def=["BIL","IEF"],
    canary=["SPY","IEF"],
    n_off=2, n_def=2, mom_fn=m13,
)
run(w, "top2 QLD/TLT/GLD/IEF")
