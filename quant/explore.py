"""
Strategy exploration — iterate from simple to complex.

We want:
    CAGR > QQQ CAGR   (~10.4%)
    Max DD <= 10%
    Sharpe > 1
    Calmar > 1.5
"""
import numpy as np
import pandas as pd

from framework import (
    load_close, synth_leveraged, build_tqqq_full, build_qld_full,
    run_backtest, compute_metrics, pretty_metrics, sma, realised_vol, zscore,
    TRADING_DAYS,
)

# ---------- universe ------------------------------------------------------
qqq = load_close("QQQ")              # 1999-03 -> 2026-04
spy = load_close("SPY")
tqqq_real = load_close("TQQQ")       # 2010-02 ->
qld_real = load_close("QLD")         # 2006-06 ->
tlt = load_close("TLT")              # 2002-07 ->
ief = load_close("IEF")
shy = load_close("SHY")
bil = load_close("BIL")              # 2007-05 ->
gld = load_close("GLD")              # 2004-11 ->
vix = load_close("^VIX")             # 1990 ->
tnx = load_close("^TNX")             # 10Y yield
irx = load_close("^IRX")             # 3M yield
xlp = load_close("XLP")              # defensive

# Backfill cash series: before BIL, use SHY; before SHY, use synthetic
# Treasury index from ^IRX.
def cash_curve() -> pd.Series:
    # Convert 3M T-bill yield to daily return curve
    yr = irx.reindex(qqq.index).ffill().bfill() / 100.0
    daily = yr / TRADING_DAYS
    syn = (1 + daily).cumprod()
    syn.name = "CASH_syn"
    return syn

cash_syn = cash_curve()

# Synthetic full-history leveraged QQQ 2x and 3x (spliced with real)
qld_full = build_qld_full(qqq, qld_real)
tqqq_full = build_tqqq_full(qqq, tqqq_real)

# Synthetic long-bond index back to 1999 using 10Y yield (duration ~17y)
def tlt_syn(ytm: pd.Series, duration: float = 17.0) -> pd.Series:
    y = ytm.reindex(qqq.index).ffill().bfill() / 100.0
    dy = y.diff().fillna(0.0)
    daily_r = y / TRADING_DAYS - duration * dy
    return (1 + daily_r).cumprod()

tlt_syn_series = tlt_syn(tnx)


def splice(real: pd.Series, synth: pd.Series) -> pd.Series:
    real = real.dropna()
    cut = real.index[0]
    pre = synth.loc[:cut].iloc[:-1]
    real_scaled = real / real.iloc[0] * synth.loc[cut]
    return pd.concat([pre, real_scaled]).sort_index()


tlt_full = splice(tlt, tlt_syn_series).reindex(qqq.index).ffill()
ief_full = splice(ief, tlt_syn(tnx, duration=7.0)).reindex(qqq.index).ffill()
bil_full = splice(bil, cash_syn).reindex(qqq.index).ffill()

# Align a master price frame; keep only days where QQQ is quoted
master = pd.DataFrame(
    {
        "QQQ": qqq,
        "QLD": qld_full.reindex(qqq.index),
        "TQQQ": tqqq_full.reindex(qqq.index),
        "BIL": bil_full,
        "IEF": ief_full,
        "TLT": tlt_full,
        "GLD": gld.reindex(qqq.index).ffill(),
    }
).dropna(subset=["QQQ"]).ffill()

print(f"Master frame: {master.index[0].date()} -> {master.index[-1].date()}  "
      f"({len(master)} rows)  cols={list(master.columns)}")

# -----------------------------------------------------------------------
# Baselines
# -----------------------------------------------------------------------
print("\n=== Baselines ===")
for tk in ["QQQ", "QLD", "TQQQ", "TLT", "IEF", "BIL"]:
    px = master[tk]
    m = compute_metrics(px / px.iloc[0])
    print(pretty_metrics(m, tk))


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def run(weights: pd.DataFrame, label: str, cols=None):
    cols = cols or list(weights.columns)
    prices = master[cols]
    w = weights[cols].reindex(prices.index).fillna(0.0)
    res = run_backtest(prices, w, cost_roundtrip=0.001)
    print(pretty_metrics(res.metrics, label))
    return res


# -----------------------------------------------------------------------
# Strategy 1  — SMA-200 timing on QQQ (baseline)
# -----------------------------------------------------------------------
print("\n=== Strategy 1: QQQ SMA-200 ===")
sig = (master["QQQ"] > sma(master["QQQ"], 200)).astype(float)
w = pd.DataFrame({"QQQ": sig.shift(1), "BIL": 1 - sig.shift(1)}).fillna(0.0)
run(w, "QQQ SMA200 -> BIL")

# -----------------------------------------------------------------------
# Strategy 2 — QLD (2x) when above SMA200 + low vol, else bonds
# -----------------------------------------------------------------------
print("\n=== Strategy 2: QLD regime ===")
vol = realised_vol(master["QQQ"], 20)
bull = (master["QQQ"] > sma(master["QQQ"], 200)) & (vol < 0.30)
w = pd.DataFrame(
    {"QLD": bull.astype(float).shift(1), "BIL": (~bull).astype(float).shift(1)}
).fillna(0.0)
run(w, "QLD if bull else BIL")

# -----------------------------------------------------------------------
# Strategy 3 — TQQQ 3x with tight risk management
# -----------------------------------------------------------------------
print("\n=== Strategy 3: TQQQ with SMA200 + vol filter ===")
bull3 = (master["QQQ"] > sma(master["QQQ"], 200)) & (vol < 0.25)
w = pd.DataFrame(
    {"TQQQ": bull3.astype(float).shift(1), "BIL": (~bull3).astype(float).shift(1)}
).fillna(0.0)
run(w, "TQQQ if bull else BIL")

# -----------------------------------------------------------------------
# Strategy 4 — Vol-targeted exposure on QQQ 2x synthetic
# Target 10% annualised vol on risky sleeve, cap leverage at 2x
# -----------------------------------------------------------------------
print("\n=== Strategy 4: Vol-target 10% on QQQ (max 2x) ===")
target = 0.10
lev = (target / vol).clip(upper=2.0).fillna(0.0)
bull = (master["QQQ"] > sma(master["QQQ"], 200))
lev_eff = lev * bull.astype(float)
# map leverage to split between QQQ, QLD, BIL
q1 = (lev_eff.clip(0, 1))            # <=1 use QQQ
q2 = (lev_eff - 1).clip(0, 1)        # >1 fraction use QLD instead
w = pd.DataFrame(
    {
        "QQQ": (q1 - q2).shift(1),   # q1 when lev<=1, goes to 0 when switching to QLD
        "QLD": q2.shift(1),
        "BIL": (1 - lev_eff.clip(0, 2) / 2 - (lev_eff.clip(1, 2) - 1) / 2).shift(1),
    }
).fillna(0.0)
# simpler: rewrite cleanly
w = pd.DataFrame(index=master.index)
w["QQQ"] = lev_eff.clip(upper=1.0)
w["QLD"] = (lev_eff - 1).clip(lower=0.0, upper=1.0) / 2  # QLD = 2x, so w=0.5 gives 1x equity
w["BIL"] = 1 - w["QQQ"] - w["QLD"]
w = w.shift(1).fillna(0.0)
run(w, "VolTarget 10% (QQQ/QLD/BIL)")

# -----------------------------------------------------------------------
# Strategy 5 — 4-asset risk parity with regime switch
# Risk on  : QLD, TLT
# Risk off : BIL, TLT, GLD
# -----------------------------------------------------------------------
print("\n=== Strategy 5: Regime-switched risk parity ===")
mon = master.resample("MS").first().index
ma50 = sma(master["QQQ"], 50)
ma200 = sma(master["QQQ"], 200)
trend_up = (master["QQQ"] > ma200) & (ma50 > ma200)
lowvol = vol < vol.rolling(252).quantile(0.7)
regime = (trend_up & lowvol).astype(int)

def inv_vol(df: pd.DataFrame, window=40):
    v = df.pct_change().rolling(window).std() * np.sqrt(TRADING_DAYS)
    inv = 1 / v
    return inv.div(inv.sum(axis=1), axis=0).fillna(0)

# risk-on sleeve
on = inv_vol(master[["QLD", "TLT"]])
# risk-off sleeve
off = inv_vol(master[["BIL", "TLT", "GLD"]])

w = pd.DataFrame(0.0, index=master.index, columns=master.columns)
mask_on = regime.reindex(w.index).fillna(0).astype(bool)
w.loc[mask_on, ["QLD", "TLT"]] = on.loc[mask_on].values
w.loc[~mask_on, ["BIL", "TLT", "GLD"]] = off.loc[~mask_on].values
# rebalance monthly
rebal = pd.Series(w.index, index=w.index).dt.to_period("M").ne(
    pd.Series(w.index, index=w.index).dt.to_period("M").shift()
)
w_m = w.where(rebal, np.nan).ffill().fillna(0.0)
run(w_m.shift(1).fillna(0.0), "Regime risk parity (mthly)")

# -----------------------------------------------------------------------
# Strategy 6 — VIX-gated TQQQ + vol-targeted sizing + trailing stop
# -----------------------------------------------------------------------
print("\n=== Strategy 6: VIX-gated TQQQ with trailing stop ===")
vix_s = vix.reindex(master.index).ffill()
vix_ma = sma(vix_s, 20)
vix_ok = (vix_s < 25) & (vix_ma < 25)
trend = master["QQQ"] > sma(master["QQQ"], 150)
sig = (vix_ok & trend).astype(float).shift(1)

target_vol = 0.10
sleeve_vol = realised_vol(master["QQQ"], 20) * 3  # TQQQ ~3x
lev = (target_vol / sleeve_vol).clip(upper=1.0)
w_tqqq = (sig * lev).fillna(0.0)
w = pd.DataFrame({"TQQQ": w_tqqq, "BIL": 1 - w_tqqq}).fillna(0.0)
run(w, "TQQQ VIX-gated voltarget")
