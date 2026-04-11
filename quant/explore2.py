"""
Second iteration: push Calmar above 1 by combining
- multi-signal regime (trend + vol + momentum)
- volatility-targeted exposure, up to 2x via QLD
- defensive IEF/GLD sleeve
- hard portfolio-level trailing stop (goes to 100% IEF)
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


def ief_syn():
    return tlt_syn(tnx, duration=7.0)


def bil_syn():
    y = irx.reindex(qqq.index).ffill().bfill() / 100.0
    daily = y / TRADING_DAYS
    return (1 + daily).cumprod()


def gld_syn():
    """Synthetic gold back to 1999 — use spot gold proxy via ^XAU? We don't
    have spot gold, but GLD starts 2004.  For 1999-2004 we simply use 0 return
    (gold was roughly flat).  Alternative: splice using TLT.  We'll use
    a conservative 4%/yr drift as a pre-inception placeholder so backtests
    are not unfairly helped by gold's 2000-2004 bull-run we can't see."""
    dates = qqq.index
    g = pd.Series(1.0, index=dates)
    rate = 0.04 / TRADING_DAYS
    g[:] = (1 + rate) ** np.arange(len(dates))
    return g


tlt_full = splice(tlt, tlt_syn(tnx)).reindex(qqq.index).ffill()
ief_full = splice(ief, ief_syn()).reindex(qqq.index).ffill()
bil_full = splice(bil, bil_syn()).reindex(qqq.index).ffill()
gld_full = splice(gld, gld_syn()).reindex(qqq.index).ffill()

master = pd.DataFrame(
    {
        "QQQ": qqq,
        "QLD": qld_full.reindex(qqq.index),
        "TQQQ": tqqq_full.reindex(qqq.index),
        "IEF": ief_full,
        "TLT": tlt_full,
        "BIL": bil_full,
        "GLD": gld_full,
    }
).dropna(subset=["QQQ"]).ffill()


def run(w, label, cols=None):
    cols = cols or list(w.columns)
    w = w[cols].reindex(master.index).fillna(0.0)
    res = run_backtest(master[cols], w, cost_roundtrip=0.001)
    print(pretty_metrics(res.metrics, label))
    return res


# -----------------------------------------------------------------------
# Helper: apply a portfolio trailing stop.
# Whenever equity drops `stop` from peak, force weights to 100% IEF
# for `cooldown` days, then allow the strategy signal to re-enter.
# -----------------------------------------------------------------------
def apply_portfolio_stop(prices, weights, stop=0.07, cooldown=20,
                         risk_off="IEF", cost=0.001):
    """Run the signal, track drawdown, force risk-off during halts."""
    w = weights.reindex(prices.index).fillna(0.0).copy()
    cols = list(w.columns)
    if risk_off not in cols:
        w[risk_off] = 0.0
        cols = list(w.columns)

    rets = prices.pct_change().fillna(0.0)
    w_arr = w.values.copy()
    r_arr = rets.values

    n, k = w_arr.shape
    equity = np.ones(n)
    port_ret = 0.0
    halt = 0
    peak = 1.0
    cost_side = cost / 2.0
    prev_w = np.zeros(k)
    ro_idx = cols.index(risk_off)

    for t in range(n):
        # Determine position for day t.
        if halt > 0:
            cur = np.zeros(k)
            cur[ro_idx] = 1.0
            halt -= 1
        else:
            cur = w_arr[t]

        turnover = np.sum(np.abs(cur - prev_w))
        cost_paid = turnover * cost_side

        # Apply cost to equity today
        if t > 0:
            equity[t] = equity[t - 1] * (1 + port_ret - cost_paid)
        else:
            equity[t] = 1.0 * (1 - cost_paid)

        peak = max(peak, equity[t])
        dd = equity[t] / peak - 1.0
        if dd <= -stop and halt == 0:
            halt = cooldown

        # Next day's return under current weights
        if t + 1 < n:
            port_ret = float(np.dot(cur, r_arr[t + 1]))
        prev_w = cur.copy()
        w_arr[t] = cur  # record the actually applied weights

    eq_s = pd.Series(equity, index=prices.index)
    pos_df = pd.DataFrame(w_arr, index=prices.index, columns=cols)
    ret_s = eq_s.pct_change().fillna(0.0)
    m = compute_metrics(eq_s, pos_df)
    return eq_s, pos_df, ret_s, m


# -----------------------------------------------------------------------
# Signals / regime
# -----------------------------------------------------------------------
px = master["QQQ"]
ma50 = sma(px, 50)
ma100 = sma(px, 100)
ma150 = sma(px, 150)
ma200 = sma(px, 200)
vol20 = realised_vol(px, 20)
vol60 = realised_vol(px, 60)

vix_s = vix.reindex(master.index).ffill()
vix_ma = sma(vix_s, 20)

# 1) Trend filter
trend = (px > ma150) & (ma50 > ma150)
# 2) Vol filter
low_vol = vol20 < 0.30
# 3) VIX filter
vix_ok = vix_s < 28
# 4) Momentum filter (3-month return positive)
mom3 = (px / px.shift(63) - 1)
mom_ok = mom3 > 0

# Composite bull
bull = trend & low_vol & vix_ok & mom_ok

# Shift signals by 1 day (executed at next open effectively = next close)
bull_x = bull.shift(1).fillna(False).astype(bool)

# -----------------------------------------------------------------------
# Strategy A: Bull → 60% QLD + 40% IEF; Bear → 100% IEF.  Monthly.
# -----------------------------------------------------------------------
print("\n=== Strategy A: bull (60% QLD + 40% IEF) / bear (IEF) ===")
w = pd.DataFrame(0.0, index=master.index, columns=["QLD", "IEF"])
w.loc[bull_x, "QLD"] = 0.6
w.loc[bull_x, "IEF"] = 0.4
w.loc[~bull_x, "IEF"] = 1.0
run(w, "A / daily")

# Monthly rebalance variant (less noise)
rebal = pd.Series(w.index, index=w.index).dt.to_period("M").ne(
    pd.Series(w.index, index=w.index).dt.to_period("M").shift()
)
w_m = w.where(rebal, np.nan).ffill().fillna(0.0)
run(w_m, "A / monthly")

# -----------------------------------------------------------------------
# Strategy B: vol-targeted QLD sleeve (target 7% annual vol) + 40% IEF
# -----------------------------------------------------------------------
print("\n=== Strategy B: vol-target 7% QLD + 40% IEF ===")
target_sleeve_vol = 0.07
# QLD realized vol = 2 * QQQ vol
lev = (target_sleeve_vol / (vol20 * 2)).clip(upper=0.75).fillna(0.0)
w = pd.DataFrame(0.0, index=master.index, columns=["QLD", "IEF", "BIL"])
w["QLD"] = lev * bull_x.astype(float)
w["IEF"] = 0.4
w["BIL"] = 1 - w["QLD"] - w["IEF"]
run(w, "B / daily")

# with portfolio stop
eq, pos, _, m = apply_portfolio_stop(master[["QLD","IEF","BIL"]], w, stop=0.07)
print(pretty_metrics(m, "B + stop 7%"))

# -----------------------------------------------------------------------
# Strategy C: Adaptive leverage via vol targeting, 5 assets, portfolio stop
# -----------------------------------------------------------------------
print("\n=== Strategy C: multi-asset vol-targeted + stop ===")
# Equity sleeve vol-target 10% using QLD (2x)
target = 0.10
equity_lev = (target / (vol20 * 2)).clip(upper=1.0).fillna(0.0)
equity_w = equity_lev * bull_x.astype(float)

# Defensive sleeve stays constant
def_w_ief = 0.50

w = pd.DataFrame(0.0, index=master.index,
                 columns=["QLD", "IEF", "GLD", "BIL"])
w["QLD"] = equity_w
w["IEF"] = def_w_ief
w["GLD"] = 0.10
w["BIL"] = (1 - w["QLD"] - w["IEF"] - w["GLD"]).clip(lower=0)
run(w, "C base")
eq, pos, _, m = apply_portfolio_stop(
    master[["QLD","IEF","GLD","BIL"]], w, stop=0.06, cooldown=30
)
print(pretty_metrics(m, "C + stop 6%"))

# -----------------------------------------------------------------------
# Strategy D: tiny QLD allocation but high hit rate on good months
# -----------------------------------------------------------------------
print("\n=== Strategy D: thin QLD + 50% IEF + 20% GLD ===")
w = pd.DataFrame(0.0, index=master.index,
                 columns=["QLD","IEF","GLD","BIL"])
w["QLD"] = 0.30 * bull_x.astype(float)
w["IEF"] = 0.50
w["GLD"] = 0.20
w["BIL"] = (1 - w["QLD"] - w["IEF"] - w["GLD"]).clip(lower=0)
# Monthly rebalance
rebal = pd.Series(w.index, index=w.index).dt.to_period("M").ne(
    pd.Series(w.index, index=w.index).dt.to_period("M").shift()
)
w_m = w.where(rebal, np.nan).ffill().fillna(0.0)
run(w_m, "D / monthly")
eq, pos, _, m = apply_portfolio_stop(
    master[["QLD","IEF","GLD","BIL"]], w_m, stop=0.07, cooldown=20
)
print(pretty_metrics(m, "D + stop 7%"))

# -----------------------------------------------------------------------
# Strategy E: tight vol target 8% across QLD+TLT+GLD
# -----------------------------------------------------------------------
print("\n=== Strategy E: multi-asset inverse-vol, gated ===")
def inv_vol(df, window=20):
    v = df.pct_change().rolling(window).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / v).fillna(0)
    return inv.div(inv.sum(axis=1), axis=0).fillna(0)

risky = master[["QLD", "TLT", "GLD"]]
w_risky = inv_vol(risky)
# Scale to target 8% vol
port_vol_est = (w_risky * risky.pct_change().rolling(20).std() * np.sqrt(TRADING_DAYS)).sum(axis=1)
scale = (0.08 / port_vol_est).clip(upper=1.0).fillna(0)
w_risky = w_risky.mul(scale, axis=0)
# gate by bull
w_risky = w_risky.mul(bull_x.astype(float), axis=0)

w = pd.DataFrame(0.0, index=master.index,
                 columns=["QLD","TLT","GLD","IEF","BIL"])
w[["QLD","TLT","GLD"]] = w_risky[["QLD","TLT","GLD"]]
w["IEF"] = 0.4
w["BIL"] = (1 - w.sum(axis=1)).clip(lower=0)
run(w, "E / daily")
eq, pos, _, m = apply_portfolio_stop(
    master[["QLD","TLT","GLD","IEF","BIL"]], w, stop=0.07, cooldown=20
)
print(pretty_metrics(m, "E + stop 7%"))
