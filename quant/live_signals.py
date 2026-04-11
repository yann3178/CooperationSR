"""
live_signals.py
===============

Run daily.  Downloads the latest prices for the Trend-Parity universe,
reproduces the exact same signal logic as the backtest, and prints the
target allocation to hold for the next session.

Usage:
    python3 live_signals.py
    python3 live_signals.py --capital 100000   # dollar sizing
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

import yfinance as yf

from strategy import RISKY, CASH, SMA_WINDOW, VOL_WINDOW, LEVERAGE
from framework import TRADING_DAYS


# ETFs actually tradeable right now (no synthetics in live mode)
LIVE_TICKERS = ["QQQ", "IEF", "GLD", "BIL"]


def download() -> pd.DataFrame:
    """Pull the most recent 2 years of OHLCV and return adjusted closes."""
    df = yf.download(LIVE_TICKERS, period="2y",
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"]
    else:
        close = df[["Close"]].rename(columns={"Close": LIVE_TICKERS[0]})
    close = close.ffill().dropna(how="all")
    return close


def compute_live_weights(prices: pd.DataFrame,
                         sma_n=SMA_WINDOW, vol_n=VOL_WINDOW,
                         leverage=LEVERAGE) -> pd.Series:
    """Compute the target weights *for today*, identical logic to backtest."""
    p = prices[RISKY].copy()
    sma = p.rolling(sma_n).mean()
    trend = p.iloc[-1] > sma.iloc[-1]
    vol = p.pct_change().rolling(vol_n).std() * np.sqrt(TRADING_DAYS)
    inv = (1.0 / vol.iloc[-1]).where(trend, 0.0).fillna(0.0)
    if inv.sum() <= 0:
        w_risky = pd.Series(0.0, index=RISKY)
    else:
        w_risky = inv / inv.sum()

    w = pd.Series(0.0, index=RISKY + [CASH])
    w[RISKY] = w_risky * leverage
    w[CASH] = 1.0 - w[RISKY].sum()
    return w


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital", type=float, default=None,
                        help="Report dollar sizing for this capital")
    parser.add_argument("--sma", type=int, default=SMA_WINDOW)
    parser.add_argument("--vol", type=int, default=VOL_WINDOW)
    parser.add_argument("--leverage", type=float, default=LEVERAGE)
    args = parser.parse_args()

    print(f"[{datetime.utcnow().isoformat()}] Downloading live prices...")
    prices = download()
    last = prices.index[-1]

    print(f"Last available close: {last.date()}")
    print(f"\nRisky universe: {RISKY}")
    print(f"Cash:           {CASH}\n")

    w = compute_live_weights(prices, args.sma, args.vol, args.leverage)

    # Diagnostic
    p = prices[RISKY].copy()
    sma = p.rolling(args.sma).mean().iloc[-1]
    price = p.iloc[-1]
    vol = (p.pct_change().rolling(args.vol).std().iloc[-1]
           * np.sqrt(TRADING_DAYS))

    print("Signal diagnostics")
    print("-" * 60)
    print(f"{'asset':<6}{'close':>10}{'sma'+str(args.sma):>12}"
          f"{'trend':>8}{'vol%':>10}")
    for c in RISKY:
        t = "ON" if price[c] > sma[c] else "OFF"
        print(f"{c:<6}{price[c]:>10.2f}{sma[c]:>12.2f}{t:>8}"
              f"{vol[c]*100:>10.2f}")

    print("\nTarget weights for tomorrow's open")
    print("-" * 60)
    for c in w.index:
        print(f"  {c:<5s} {w[c]*100:+7.2f}%")
    print("-" * 60)
    print(f"  gross long : {w[w > 0].sum()*100:.2f}%")
    print(f"  short BIL  : {min(w[CASH], 0)*100:.2f}% (financed leverage)")

    if args.capital:
        print(f"\nDollar sizing on ${args.capital:,.0f} capital:")
        for c in w.index:
            dollars = args.capital * w[c]
            last_px = prices[c].iloc[-1] if c in prices.columns else np.nan
            shares = dollars / last_px if last_px and last_px > 0 else np.nan
            print(f"  {c:<5s} ${dollars:+12,.0f}   "
                  f"({shares:+8.1f} shares @ ${last_px:.2f})")

    # Next rebalance note
    today = last + pd.Timedelta(days=1)
    next_rebal = (today.to_period("M") + 1).to_timestamp()
    print(f"\nNext full rebalance: first trading day on/after "
          f"{next_rebal.date()}")
    print("(the strategy rebalances once per calendar month)")


if __name__ == "__main__":
    main()
