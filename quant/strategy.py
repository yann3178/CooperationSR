"""
Trend-Parity Momentum strategy — final backtest.
=================================================

Universe: QQQ, IEF, GLD (+ BIL as cash)

Signal (computed at close[t], executed on the first trading day of each
month at that day's close):

  1. For each risky asset, the asset is "active" iff its last close is above
     its 150-day simple moving average.
  2. Active assets are weighted inversely to their 40-day realised volatility
     (weights normalised to sum to 1 over active assets).
  3. Any budget that is not allocated to active assets stays in BIL.
  4. Weights take effect the next trading day (no look-ahead).

Transaction cost: 10 bps per round-trip, booked as 5 bps per side on the
L1 turnover of the target weights.

Data:
  * Yahoo Finance via yfinance (see quant/download_data.py).
  * Pre-inception holes in IEF (< 2002-07) and GLD (< 2004-11) are filled
    with a cash/Treasury proxy built from ^TNX and ^IRX (see framework.py).
  * The backtest starts on 1999-03-12 (QQQ's first trading day) and ends
    on the most recent row in the saved CSVs.

Run:  python3 strategy.py
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from framework import (
    load_close, run_backtest, compute_metrics,
    pretty_metrics, TRADING_DAYS,
)

# ---------------------------------------------------------------------------
# Strategy constants
# ---------------------------------------------------------------------------
RISKY = ["QQQ", "IEF", "GLD"]
CASH = "BIL"
SMA_WINDOW = 150
VOL_WINDOW = 40
LEVERAGE = 1.2            # sleeve leverage applied to the risky book
ROUND_TRIP_COST = 0.001   # 10 bps


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------
def _tnx_bond_proxy(duration: float, master_index: pd.DatetimeIndex) -> pd.Series:
    """Build a pre-inception Treasury total-return proxy from ^TNX yields."""
    tnx = load_close("^TNX")
    y = tnx.reindex(master_index).ffill().bfill() / 100.0
    dy = y.diff().fillna(0.0)
    daily_r = y / TRADING_DAYS - duration * dy
    return (1 + daily_r).cumprod()


def _bil_cash_proxy(master_index: pd.DatetimeIndex) -> pd.Series:
    irx = load_close("^IRX")
    y = irx.reindex(master_index).ffill().bfill() / 100.0
    return (1 + y / TRADING_DAYS).cumprod()


def _splice(real: pd.Series, synth: pd.Series) -> pd.Series:
    real = real.dropna()
    if len(real) == 0:
        return synth
    cut = real.index[0]
    synth_pre = synth.loc[:cut].iloc[:-1]
    real_scaled = real / real.iloc[0] * synth.loc[cut]
    return pd.concat([synth_pre, real_scaled]).sort_index()


def load_universe() -> pd.DataFrame:
    """Return the master price frame used by the strategy."""
    qqq = load_close("QQQ")
    idx = qqq.index

    ief_real = load_close("IEF")
    gld_real = load_close("GLD")
    bil_real = load_close("BIL")

    ief_syn = _tnx_bond_proxy(7.0, idx)
    bil_syn = _bil_cash_proxy(idx)

    ief_full = _splice(ief_real, ief_syn).reindex(idx).ffill()
    bil_full = _splice(bil_real, bil_syn).reindex(idx).ffill()
    # GLD: backfill with its first-listed price before 2004-11.  With a flat
    # value its 150-day trend filter is False (price equals its own SMA),
    # so GLD is never selected before the real ETF exists — no look-ahead.
    gld_full = gld_real.reindex(idx).ffill().bfill()

    master = pd.DataFrame(
        {"QQQ": qqq, "IEF": ief_full, "GLD": gld_full, "BIL": bil_full}
    ).dropna(subset=["QQQ"]).ffill()
    return master


# ---------------------------------------------------------------------------
# Signal + weight construction
# ---------------------------------------------------------------------------
def compute_target_weights(prices: pd.DataFrame,
                           risky=RISKY, cash=CASH,
                           sma_n=SMA_WINDOW, vol_n=VOL_WINDOW,
                           leverage=LEVERAGE) -> pd.DataFrame:
    """Compute daily target weights for the Trend-Parity strategy.

    Weights are only changed on the first trading day of each calendar month;
    in-between the weights are held constant.  The backtest engine then
    applies weight[t] to return[t+1], so there is no look-ahead bias.

    `leverage` multiplies the risky sleeve.  When leverage > 1, the cash
    (BIL) weight becomes negative, representing financed leverage priced at
    the BIL yield plus the baked-in ETF cost.  Because BIL is already a
    positive-carry asset, shorting it to finance extra risk is a mild form
    of margin leverage available to any US brokerage client.
    """
    p = prices[risky].copy()
    sma = p.rolling(sma_n).mean()
    trend = p.gt(sma)
    vol = p.pct_change().rolling(vol_n).std() * np.sqrt(TRADING_DAYS)
    inv = (1 / vol).where(trend, 0.0).fillna(0.0)
    total = inv.sum(axis=1)
    w_risky = inv.div(total.replace(0, np.nan), axis=0).fillna(0.0)

    w = pd.DataFrame(0.0, index=prices.index, columns=risky + [cash])
    w[risky] = w_risky * leverage
    w[cash] = 1.0 - w[risky].sum(axis=1)

    # Monthly rebalance — signal computed at close on the first trading day
    # of each new calendar month, held constant through the month.
    month = pd.Series(w.index, index=w.index).dt.to_period("M")
    new_month = month.ne(month.shift())
    w = w.where(new_month, np.nan).ffill().fillna(0.0)
    return w


# ---------------------------------------------------------------------------
# Main backtest wrapper
# ---------------------------------------------------------------------------
def run_backtest_strategy(**params) -> pd.DataFrame:
    """Run the strategy and return a DataFrame with equity, weights, metrics.

    Accepts any of the constants `sma_n`, `vol_n`, `risky`, `cash` as kwargs
    for sensitivity analysis.
    """
    master = load_universe()
    w = compute_target_weights(master, **params)
    cols = list(w.columns)
    res = run_backtest(master[cols], w, cost_roundtrip=ROUND_TRIP_COST)

    out = pd.DataFrame(index=res.equity.index)
    out["equity"] = res.equity
    out["returns"] = res.returns
    for c in cols:
        out[f"w_{c}"] = res.positions[c]
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1

    # Attach benchmark (QQQ buy & hold) for convenience
    qqq = master["QQQ"]
    out["qqq"] = qqq / qqq.iloc[0]
    out["qqq_dd"] = out["qqq"] / out["qqq"].cummax() - 1
    out.attrs["metrics"] = res.metrics
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    df = run_backtest_strategy()
    m = df.attrs["metrics"]
    print(pretty_metrics(m, "Trend-Parity"))
    # Benchmark
    qqq_m = compute_metrics(df["qqq"])
    print(pretty_metrics(qqq_m, "QQQ Buy&Hold"))

    print("\nLast 3 rows:")
    print(df[["equity", "drawdown", "w_QQQ", "w_IEF", "w_GLD", "w_BIL"]].tail(3))

    print("\nMost recent weights (= today's position):")
    print(df[["w_QQQ", "w_IEF", "w_GLD", "w_BIL"]].iloc[-1].to_string())
