"""
Backtest framework + utilities.

Key design choices
------------------
- Signals are computed on day t using data up to and including close[t].
- Positions are executed at close[t] (no look-ahead, no intraday fills).
- P&L on day t+1 is position(t) * return(t+1).
- Transaction costs: 0.10% per *round-trip*, modelled as 0.05% on every change
  of notional exposure (one-way). Turnover on day t is |w_t - w_{t-1}|.
- Drawdowns, CAGR, Sharpe are computed on the daily equity curve.
- Synthetic leveraged ETFs: when a real ticker is unavailable (before its
  inception), we synthesize one from the underlying's daily return r via
  r_lev = L * r - (expense_ratio + L * borrow_spread) / 252
  This is the standard academic approximation, consistent with how PROFUNDS
  has constructed pre-inception simulation for QLD / TQQQ.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_ticker(ticker: str) -> pd.DataFrame:
    path = os.path.join(
        DATA_DIR, f"{ticker.replace('^', '').replace('=','')}.csv"
    )
    df = pd.read_csv(path, skiprows=[1, 2], parse_dates=[0], index_col=0)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def load_close(ticker: str) -> pd.Series:
    df = load_ticker(ticker)
    # After skiprows the first remaining row holds yfinance headers; the first
    # numerical column is Close (auto_adjust=True).
    s = df["Close"].astype(float)
    s.name = ticker
    return s


def closes(tickers) -> pd.DataFrame:
    out = pd.concat([load_close(t) for t in tickers], axis=1)
    return out


# ---------------------------------------------------------------------------
# Synthetic leveraged ETFs
# ---------------------------------------------------------------------------
def synth_leveraged(
    underlying: pd.Series,
    leverage: float,
    expense: float = 0.0095,   # TQQQ ~0.88%, QLD ~0.95%
    borrow: float = 0.004,     # overnight financing haircut
) -> pd.Series:
    r = underlying.pct_change().fillna(0.0)
    daily_cost = (expense + leverage * borrow) / TRADING_DAYS
    r_lev = leverage * r - daily_cost
    px = (1.0 + r_lev).cumprod()
    px = px / px.iloc[0] * 100.0
    px.name = f"{underlying.name}_x{leverage:g}"
    return px


def build_tqqq_full(
    qqq: pd.Series, real_tqqq: Optional[pd.Series] = None
) -> pd.Series:
    """Return a TQQQ-like price series that covers QQQ's full history."""
    synth = synth_leveraged(qqq, 3.0)
    if real_tqqq is None:
        return synth
    real = real_tqqq.dropna()
    # Splice: use synth before real inception, real afterwards.
    cutoff = real.index[0]
    synth_pre = synth.loc[:cutoff].iloc[:-1]
    real_scaled = real / real.iloc[0] * synth.loc[cutoff]
    return pd.concat([synth_pre, real_scaled]).sort_index()


def build_qld_full(
    qqq: pd.Series, real_qld: Optional[pd.Series] = None
) -> pd.Series:
    synth = synth_leveraged(qqq, 2.0, expense=0.0095, borrow=0.003)
    if real_qld is None:
        return synth
    real = real_qld.dropna()
    cutoff = real.index[0]
    synth_pre = synth.loc[:cutoff].iloc[:-1]
    real_scaled = real / real.iloc[0] * synth.loc[cutoff]
    return pd.concat([synth_pre, real_scaled]).sort_index()


# ---------------------------------------------------------------------------
# Performance analytics
# ---------------------------------------------------------------------------
@dataclass
class Metrics:
    start: pd.Timestamp
    end: pd.Timestamp
    cagr: float
    vol: float
    sharpe: float
    sortino: float
    max_dd: float
    calmar: float
    turnover: float
    num_trades: int
    final_equity: float

    def as_dict(self) -> Dict[str, float]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def compute_metrics(
    equity: pd.Series, positions: Optional[pd.DataFrame] = None
) -> Metrics:
    equity = equity.dropna()
    rets = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    sharpe = rets.mean() / rets.std() * np.sqrt(TRADING_DAYS) if rets.std() > 0 else 0.0
    neg = rets[rets < 0]
    sortino = rets.mean() / neg.std() * np.sqrt(TRADING_DAYS) if len(neg) > 0 and neg.std() > 0 else 0.0
    dd = equity / equity.cummax() - 1.0
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else 0.0

    turnover = 0.0
    num_trades = 0
    if positions is not None:
        delta = positions.diff().abs().sum(axis=1).fillna(0.0)
        turnover = float(delta.sum() / years)
        # a "trade" = any day where any instrument's weight changes by > 1bp
        num_trades = int((positions.diff().abs().sum(axis=1) > 1e-4).sum())

    return Metrics(
        start=equity.index[0],
        end=equity.index[-1],
        cagr=float(cagr),
        vol=float(vol),
        sharpe=float(sharpe),
        sortino=float(sortino),
        max_dd=float(max_dd),
        calmar=float(calmar),
        turnover=float(turnover),
        num_trades=int(num_trades),
        final_equity=float(equity.iloc[-1]),
    )


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------
@dataclass
class BacktestResult:
    equity: pd.Series
    positions: pd.DataFrame          # daily target weights (after exec)
    returns: pd.Series
    metrics: Metrics
    prices: pd.DataFrame = field(repr=False)


def run_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_roundtrip: float = 0.001,
    start_capital: float = 1.0,
) -> BacktestResult:
    """Execute a portfolio described by target_weights.

    Parameters
    ----------
    prices : DataFrame of close prices, columns = instruments
    target_weights : DataFrame aligned with prices; weight applied at close[t]
        earns return[t+1].  Weights may sum to anything (cash = 1 - sum).
    cost_roundtrip : 0.001 = 10 bps round-trip.  Applied as cost/2 per side on
        turnover (|Δw|).
    """
    prices = prices.dropna(how="all")
    target_weights = target_weights.reindex(prices.index).fillna(0.0)

    rets = prices.pct_change().fillna(0.0)

    w = target_weights.values
    r = rets.values
    n, k = w.shape

    equity = np.ones(n)
    port_ret = np.zeros(n)
    applied_w = np.zeros_like(w)

    prev_w = np.zeros(k)
    cost_side = cost_roundtrip / 2.0

    for t in range(n):
        # Execute target at close[t]; pay turnover cost on day t.
        turnover = np.sum(np.abs(w[t] - prev_w))
        cost = turnover * cost_side

        # The position now in effect earns next day's return.
        if t + 1 < n:
            port_ret[t + 1] = float(np.dot(w[t], r[t + 1]))
        # Subtract cost from today's P&L.
        if t > 0:
            equity[t] = equity[t - 1] * (1 + port_ret[t] - cost)
        else:
            equity[t] = 1.0 * (1 - cost)

        applied_w[t] = w[t]
        prev_w = w[t]

    eq_s = pd.Series(equity * start_capital, index=prices.index, name="equity")
    pos_df = pd.DataFrame(applied_w, index=prices.index, columns=prices.columns)
    ret_s = pd.Series(port_ret, index=prices.index, name="ret")

    m = compute_metrics(eq_s, pos_df)
    return BacktestResult(eq_s, pos_df, ret_s, m, prices)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=max(2, n // 2)).mean()


def realised_vol(s: pd.Series, window: int = 20, ann: int = TRADING_DAYS) -> pd.Series:
    r = s.pct_change()
    return r.rolling(window, min_periods=window // 2).std() * np.sqrt(ann)


def zscore(s: pd.Series, window: int) -> pd.Series:
    mu = s.rolling(window).mean()
    sd = s.rolling(window).std()
    return (s - mu) / sd


def rolling_max_dd(s: pd.Series, window: int) -> pd.Series:
    def _dd(x):
        peak = np.maximum.accumulate(x)
        return (x[-1] - peak[-1]) / peak[-1] if peak[-1] > 0 else 0.0
    return s.rolling(window, min_periods=window // 2).apply(_dd, raw=True)


def pretty_metrics(m: Metrics, label: str = "") -> str:
    return (
        f"{label:<22s} "
        f"CAGR {m.cagr*100:6.2f}%  "
        f"Vol {m.vol*100:5.2f}%  "
        f"Sharpe {m.sharpe:4.2f}  "
        f"Sortino {m.sortino:4.2f}  "
        f"MaxDD {m.max_dd*100:6.2f}%  "
        f"Calmar {m.calmar:4.2f}  "
        f"Turnover {m.turnover:5.2f}  "
        f"Trades {m.num_trades}  "
        f"[{m.start.date()} -> {m.end.date()}]"
    )
