"""
Iteration 8: converge on the best architecture.

Core approach:
  risky universe = {QQQ or QLD, TLT, GLD}
  each asset gated by SMA trend filter (100-200 day)
  inverse-vol weighting among the gated assets
  unused budget in BIL
  monthly rebalance (first trading day of each month)
  drawdown safety: if portfolio is > X% below its 252-day rolling high,
    linearly scale gross exposure down.

Grid search parameters to find the best Calmar and best CAGR w/ DD<=15%.
"""
import numpy as np
import pandas as pd
import itertools
from framework import (
    load_close, build_qld_full, run_backtest, compute_metrics,
    pretty_metrics, sma, realised_vol, TRADING_DAYS,
)

# ------------------ data ------------------
qqq = load_close("QQQ")
tlt = load_close("TLT")
ief = load_close("IEF")
bil = load_close("BIL")
gld = load_close("GLD")
tnx = load_close("^TNX")
irx = load_close("^IRX")
qld_full = build_qld_full(qqq, load_close("QLD"))


def tlt_syn(d=17):
    y = tnx.reindex(qqq.index).ffill().bfill() / 100.0
    dy = y.diff().fillna(0.0)
    return (1 + y / TRADING_DAYS - d * dy).cumprod()


def bil_syn():
    y = irx.reindex(qqq.index).ffill().bfill() / 100.0
    return (1 + y / TRADING_DAYS).cumprod()


def splice(real, synth):
    real = real.dropna()
    cut = real.index[0]
    pre = synth.loc[:cut].iloc[:-1]
    rs = real / real.iloc[0] * synth.loc[cut]
    return pd.concat([pre, rs]).sort_index()


idx = qqq.index
master = pd.DataFrame({
    "QQQ": qqq,
    "QLD": qld_full.reindex(idx),
    "TLT": splice(tlt, tlt_syn(17)).reindex(idx).ffill(),
    "IEF": splice(ief, tlt_syn(7)).reindex(idx).ffill(),
    "GLD": gld.reindex(idx).ffill().bfill(),
    "BIL": splice(bil, bil_syn()).reindex(idx).ffill(),
}).dropna(subset=["QQQ"]).ffill()

eom = pd.Series(master.index, index=master.index).dt.to_period("M")
rebal = eom.ne(eom.shift())


def base_strat(risky, sma_n, vol_win, lev=1.0):
    """Inverse-vol trend-gated weights + BIL for the remainder."""
    prices = master[risky]
    trend = prices.gt(prices.rolling(sma_n).mean())
    v = prices.pct_change().rolling(vol_win).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / v).fillna(0).where(trend, 0.0)
    tot = inv.sum(axis=1)
    w_iv = inv.div(tot.replace(0, np.nan), axis=0).fillna(0)
    w = pd.DataFrame(0.0, index=master.index, columns=risky + ["BIL"])
    w[risky] = w_iv * lev
    w["BIL"] = 1 - w[risky].sum(axis=1)
    return w.where(rebal, np.nan).ffill().fillna(0.0)


def dd_overlay_run(prices, base_w, dd_start=0.08, dd_end=0.15,
                   peak_window=252, cooldown_days=5, cost=0.001,
                   risk_off="BIL"):
    """
    Run strategy with soft drawdown scaling.

    scale = 1  when dd > -dd_start
    scale  linear down to 0 as dd approaches -dd_end
    After a trigger, require `cooldown_days` above dd_start/2 before scaling back up.
    """
    base_w = base_w.reindex(prices.index).fillna(0.0)
    cols = list(base_w.columns)
    if risk_off not in cols:
        cols = cols + [risk_off]
        base_w[risk_off] = 0.0

    rets_all = prices.reindex(columns=cols).pct_change().fillna(0.0).values
    n, k = rets_all.shape
    base_vals = base_w[cols].values
    ro_i = cols.index(risk_off)

    equity = np.ones(n)
    prev = np.zeros(k)
    applied = np.zeros_like(base_vals)
    peak_equity = 1.0
    cost_side = cost / 2.0
    peak_hist = np.ones(peak_window)
    ph_idx = 0
    scale_prev = 1.0
    days_since_trig = cooldown_days

    for t in range(n):
        # rolling max over last `peak_window` days
        peak = max(np.max(peak_hist), equity[t - 1] if t > 0 else 1.0)
        dd = (equity[t - 1] / peak - 1.0) if t > 0 else 0.0
        if dd >= -dd_start:
            target_scale = 1.0
        elif dd <= -dd_end:
            target_scale = 0.0
        else:
            target_scale = (dd + dd_end) / (dd_end - dd_start)
            target_scale = max(0.0, min(1.0, target_scale))

        # sticky scale: don't rise faster than 1/cooldown_days per day
        if target_scale < scale_prev:
            scale = target_scale
            days_since_trig = 0
        else:
            days_since_trig += 1
            scale = scale_prev + min(1 / cooldown_days,
                                     target_scale - scale_prev)
        scale = max(0.0, min(1.0, scale))

        cur = base_vals[t].copy()
        risky_mask = np.arange(k) != ro_i
        cur_risky = cur * 0
        cur_risky[risky_mask] = cur[risky_mask] * scale
        cur_final = cur_risky.copy()
        cur_final[ro_i] = 1 - cur_risky.sum()

        turnover = np.sum(np.abs(cur_final - prev))
        cost_paid = turnover * cost_side
        if t > 0:
            r = float(np.dot(prev, rets_all[t]))
            equity[t] = equity[t - 1] * (1 + r - cost_paid)
        else:
            equity[t] = 1.0 - cost_paid

        peak_hist[ph_idx] = equity[t]
        ph_idx = (ph_idx + 1) % peak_window
        applied[t] = cur_final
        prev = cur_final.copy()
        scale_prev = scale

    eq_s = pd.Series(equity, index=prices.index)
    pos_df = pd.DataFrame(applied, index=prices.index, columns=cols)
    m = compute_metrics(eq_s, pos_df)
    return eq_s, pos_df, m


# ---------------- Grid search ----------------
results = []
universes = [
    ["QQQ", "TLT", "GLD"],
    ["QLD", "TLT", "GLD"],
    ["QQQ", "IEF", "GLD"],
    ["QQQ", "TLT", "GLD", "IEF"],
    ["QLD", "IEF", "GLD"],
]
sma_choices = [100, 125, 150, 175, 200]
vol_choices = [20, 40, 60]
lev_choices = [1.0, 1.2, 1.4]

print("Running base grid...")
for uni, s, vw, lev in itertools.product(universes, sma_choices,
                                          vol_choices, lev_choices):
    w = base_strat(uni, s, vw, lev)
    prices = master[list(w.columns)]
    # cap risk if leverage used
    res = run_backtest(prices, w)
    m = res.metrics
    results.append(dict(
        uni=uni, sma=s, vw=vw, lev=lev,
        overlay="none",
        cagr=m.cagr, dd=m.max_dd, sharpe=m.sharpe,
        calmar=m.calmar, vol=m.vol, turnover=m.turnover,
    ))

res_df = pd.DataFrame(results)
print(f"Tested {len(res_df)} base configurations.")

# Filter: MaxDD is reasonable, sort by CAGR
print("\nTop by Calmar:")
top = res_df.sort_values("calmar", ascending=False).head(10)
for _, r in top.iterrows():
    print(f"  uni={r['uni']} sma={r['sma']} vw={r['vw']} lev={r['lev']:.1f}  "
          f"CAGR {r['cagr']*100:5.2f}%  DD {r['dd']*100:6.2f}%  "
          f"Sharpe {r['sharpe']:.2f}  Calmar {r['calmar']:.2f}")

print("\nTop by CAGR (DD < 20%):")
mask = res_df["dd"] > -0.20
top_cagr = res_df[mask].sort_values("cagr", ascending=False).head(10)
for _, r in top_cagr.iterrows():
    print(f"  uni={r['uni']} sma={r['sma']} vw={r['vw']} lev={r['lev']:.1f}  "
          f"CAGR {r['cagr']*100:5.2f}%  DD {r['dd']*100:6.2f}%  "
          f"Sharpe {r['sharpe']:.2f}  Calmar {r['calmar']:.2f}")

print("\nTop by CAGR (DD < 15%):")
mask = res_df["dd"] > -0.15
top_cagr = res_df[mask].sort_values("cagr", ascending=False).head(10)
for _, r in top_cagr.iterrows():
    print(f"  uni={r['uni']} sma={r['sma']} vw={r['vw']} lev={r['lev']:.1f}  "
          f"CAGR {r['cagr']*100:5.2f}%  DD {r['dd']*100:6.2f}%  "
          f"Sharpe {r['sharpe']:.2f}  Calmar {r['calmar']:.2f}")

print("\nTop by CAGR (DD < 12%):")
mask = res_df["dd"] > -0.12
top_cagr = res_df[mask].sort_values("cagr", ascending=False).head(10)
for _, r in top_cagr.iterrows():
    print(f"  uni={r['uni']} sma={r['sma']} vw={r['vw']} lev={r['lev']:.1f}  "
          f"CAGR {r['cagr']*100:5.2f}%  DD {r['dd']*100:6.2f}%  "
          f"Sharpe {r['sharpe']:.2f}  Calmar {r['calmar']:.2f}")
