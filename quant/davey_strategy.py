"""
Kevin Davey's simple breakout algorithm applied monthly to the ETF universe
SPY / XLF / EEM / GLD / USO.

Original EasyLanguage rules:
    input: x1(4), x2(5);
    If not in market AND close[0] - close[x1] >= 0
        then buy next bar at market;
    If close[0] - close[x2] < 0
        then sell next bar at market;

Monthly timeframe -> x1 = 4 months, x2 = 5 months.

Semantics:
    Entry:  at month-end t, if current monthly close >= monthly close
            of 4 months ago and we are flat, go long from the next month's
            first trading day, held at 100% notional on that ETF.
    Exit:   at month-end t, if current monthly close < monthly close
            of 5 months ago and we are long, exit at the next month's
            first trading day.

Portfolio:
    Equal-weighted across the 5 ETFs (20% max each).  Unused budget
    parked in BIL.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from framework import (
    load_close, run_backtest, compute_metrics, pretty_metrics, TRADING_DAYS,
)

DAVEY_TICKERS = ["SPY", "XLF", "EEM", "GLD", "USO"]
CASH = "BIL"
X1 = 4    # entry lookback in months
X2 = 5    # exit lookback in months
START_DATE = "2006-12-29"   # from original input: date >= 1061229


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_davey_universe() -> pd.DataFrame:
    prices = {}
    for t in DAVEY_TICKERS:
        s = load_close(t)
        prices[t] = s
    # Cash series — extend BIL with ^IRX carry pre-2007
    bil = load_close("BIL")
    irx = load_close("^IRX")
    # Build a single master index (union)
    idx = sorted(set().union(*[p.index for p in prices.values()]))
    idx = pd.DatetimeIndex(idx)

    y = irx.reindex(idx).ffill().bfill() / 100.0
    bil_syn = (1 + y / TRADING_DAYS).cumprod()
    cut = bil.index[0]
    bil_full = pd.concat(
        [bil_syn.loc[:cut].iloc[:-1],
         bil / bil.iloc[0] * bil_syn.loc[cut]]
    ).sort_index().reindex(idx).ffill()

    master = pd.DataFrame(prices).reindex(idx).ffill()
    master[CASH] = bil_full
    # Drop any leading rows where SPY is missing (SPY has the longest history)
    master = master.dropna(subset=["SPY"])
    return master


# ---------------------------------------------------------------------------
# Davey signal: monthly breakout
# ---------------------------------------------------------------------------
def davey_monthly_signal(prices: pd.DataFrame, x1: int = X1, x2: int = X2
                         ) -> pd.DataFrame:
    """Return a daily DataFrame of {0, 1} positions for each ETF.

    Signal is evaluated at each calendar month-end on the monthly close.
    The resulting position takes effect on the first trading day of the
    following month (no look-ahead).
    """
    # Monthly end-of-month close — use "last observed" close each month.
    m = prices.resample("ME").last()
    n, k = m.shape
    in_mkt = np.zeros((n, k), dtype=float)
    for i in range(max(x1, x2), n):
        for j in range(k):
            prev = in_mkt[i - 1, j] if i > 0 else 0.0
            c0 = m.iloc[i, j]
            c1 = m.iloc[i - x1, j]   # 4 months ago
            c2 = m.iloc[i - x2, j]   # 5 months ago
            if prev == 0.0:
                # Entry: if c0 >= c1, go long for NEXT bar
                if c0 - c1 >= 0:
                    in_mkt[i, j] = 1.0
                else:
                    in_mkt[i, j] = 0.0
            else:
                # Exit if c0 < c2
                if c0 - c2 < 0:
                    in_mkt[i, j] = 0.0
                else:
                    in_mkt[i, j] = 1.0

    monthly_pos = pd.DataFrame(in_mkt, index=m.index, columns=m.columns)

    # Apply start-date filter: no entries before START_DATE
    start = pd.Timestamp(START_DATE)
    monthly_pos.loc[:start] = 0.0

    # Lag by one month: the signal at month-end t takes effect in month t+1.
    monthly_pos_exec = monthly_pos.shift(1).fillna(0.0)

    # Map to daily: the monthly weight becomes effective on the first
    # trading day of the next calendar month.
    daily_pos = monthly_pos_exec.reindex(prices.index, method=None)
    daily_pos = daily_pos.ffill().fillna(0.0)
    return daily_pos


def davey_portfolio_weights(prices: pd.DataFrame, weight_per_etf: float = 0.2,
                            x1: int = X1, x2: int = X2) -> pd.DataFrame:
    """Equal-weight portfolio: 20% per ETF when long, rest in cash."""
    sig = davey_monthly_signal(prices[DAVEY_TICKERS], x1, x2)
    w = pd.DataFrame(0.0, index=prices.index, columns=DAVEY_TICKERS + [CASH])
    w[DAVEY_TICKERS] = sig * weight_per_etf
    w[CASH] = 1.0 - w[DAVEY_TICKERS].sum(axis=1)
    return w


# ---------------------------------------------------------------------------
# Main: run and report
# ---------------------------------------------------------------------------
def main():
    master = load_davey_universe()
    print(f"Master: {master.index[0].date()} -> {master.index[-1].date()}  "
          f"({len(master)} rows)")

    # Full portfolio (default 20% each)
    w = davey_portfolio_weights(master)
    cols = list(w.columns)
    prices = master[cols]

    # Trim to the interesting window
    start_bt = pd.Timestamp("2007-01-01")
    mask = prices.index >= start_bt
    prices_bt = prices.loc[mask]
    w_bt = w.loc[mask]

    res = run_backtest(prices_bt, w_bt, cost_roundtrip=0.001)
    m = res.metrics
    print("\nKevin Davey monthly 4/5 breakout — 5-ETF portfolio:")
    print(pretty_metrics(m, "Davey 5-ETF"))

    # Compare to QQQ and SPY buy & hold over the same window
    qqq = load_close("QQQ").loc[prices_bt.index[0]:]
    spy_bh = master["SPY"].loc[prices_bt.index[0]:]
    qqq_eq = qqq / qqq.iloc[0]
    spy_eq = spy_bh / spy_bh.iloc[0]
    print(pretty_metrics(compute_metrics(qqq_eq), "QQQ B&H (same window)"))
    print(pretty_metrics(compute_metrics(spy_eq), "SPY B&H (same window)"))

    # Per-ETF stand-alone stats
    print("\nPer-ETF stand-alone (100% per signal, rest in BIL):")
    for tk in DAVEY_TICKERS:
        w_single = pd.DataFrame(0.0, index=prices_bt.index,
                                columns=[tk, CASH])
        sig = davey_monthly_signal(master[[tk]]).loc[prices_bt.index]
        w_single[tk] = sig[tk]
        w_single[CASH] = 1 - w_single[tk]
        r = run_backtest(prices_bt[[tk, CASH]], w_single)
        print(pretty_metrics(r.metrics, f"  {tk}"))

    # Parameter sensitivity on the portfolio
    print("\nGrid search (x1, x2):")
    for x1 in [3, 4, 5, 6]:
        for x2 in [3, 4, 5, 6, 7, 8]:
            w_p = davey_portfolio_weights(master, x1=x1, x2=x2).loc[mask]
            r = run_backtest(prices_bt, w_p, cost_roundtrip=0.001)
            mm = r.metrics
            print(f"  x1={x1} x2={x2}  "
                  f"CAGR {mm.cagr*100:5.2f}%  DD {mm.max_dd*100:6.2f}%  "
                  f"Sharpe {mm.sharpe:.2f}  Calmar {mm.calmar:.2f}")

    return res


if __name__ == "__main__":
    main()
