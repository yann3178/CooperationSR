"""cb_twap_engine.py -- Share-based backtest engine with OHLCV support"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

SYMBOLS = ['QQQ', 'TLT', 'GLD', 'VNQ']
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data_ohlcv')
TRADING_DAYS = 252
SMA_WINDOW = 150
VOL_WINDOW = 40

def load_ohlcv(sym: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f'{sym}.csv')
    df = pd.read_csv(path, skiprows=[1, 2], parse_dates=[0], index_col=0)
    df = df.rename(columns=lambda c: c.strip()).sort_index()
    df = df[~df.index.duplicated(keep='last')]
    return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)

def load_all_ohlcv(symbols=None):
    symbols = symbols or SYMBOLS
    return {s: load_ohlcv(s) for s in symbols}

def build_aligned_frames(ohlcv):
    open_px = pd.concat({s: ohlcv[s]['Open'] for s in ohlcv}, axis=1).dropna()
    high_px = pd.concat({s: ohlcv[s]['High'] for s in ohlcv}, axis=1).dropna()
    low_px = pd.concat({s: ohlcv[s]['Low'] for s in ohlcv}, axis=1).dropna()
    close_px = pd.concat({s: ohlcv[s]['Close'] for s in ohlcv}, axis=1).dropna()
    common = open_px.index.intersection(high_px.index).intersection(low_px.index).intersection(close_px.index)
    return open_px.loc[common], high_px.loc[common], low_px.loc[common], close_px.loc[common]

def tp_weights_on_date(date, close_px, sma, vol):
    symbols = list(close_px.columns)
    try: p, s, v = close_px.loc[date], sma.loc[date], vol.loc[date]
    except KeyError: return {sym: 0.0 for sym in symbols}
    inv = {}
    for sym in symbols:
        if p[sym] > s[sym] and v[sym] > 0 and not np.isnan(v[sym]): inv[sym] = 1.0/v[sym]
        else: inv[sym] = 0.0
    total = sum(inv.values())
    return {sym: inv[sym]/total for sym in symbols} if total > 0 else {sym: 0.0 for sym in symbols}

def get_exec_price(mode, day_idx, sym, open_px, high_px, low_px, close_px):
    n = len(close_px)
    if mode == 'open': return float(open_px.iloc[day_idx][sym])
    elif mode == 'close': return float(close_px.iloc[day_idx][sym])
    elif mode == 'ohlc_avg':
        return (float(open_px.iloc[day_idx][sym]) + float(high_px.iloc[day_idx][sym]) + float(low_px.iloc[day_idx][sym]) + float(close_px.iloc[day_idx][sym])) / 4.0
    elif mode == 'twap_2d':
        prices = [float(close_px.iloc[min(day_idx+j, n-1)][sym]) for j in range(2)]
        return np.mean(prices)
    elif mode == 'twap_3d':
        prices = [float(close_px.iloc[min(day_idx+j, n-1)][sym]) for j in range(3)]
        return np.mean(prices)
    return float(open_px.iloc[day_idx][sym])

@dataclass
class CBEvent:
    date: object; portfolio_value: float; peak_value: float; drawdown_pct: float
    reentry_date: object = None; reentry_value: float = None
    qqq_fwd_1d: float = None; qqq_fwd_5d: float = None; qqq_fwd_21d: float = None
    trigger_date: object = None; trigger_dd: float = None; fwd_21d_ret: float = None

@dataclass
class BacktestResult:
    dates: object; equity: object; equity_intraday_high: object; equity_intraday_low: object
    cash_series: object; in_cash_mode: object; cb_events: list = field(default_factory=list)
    config: dict = field(default_factory=dict)

@dataclass
class Metrics:
    cagr: float; vol: float; sharpe: float; max_dd_close: float; max_dd_intraday: float
    calmar: float; profit_factor: float; final_equity: float; years: float

def compute_metrics(result):
    equity = pd.Series(result.equity, index=result.dates).dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0: return Metrics(0,0,0,0,0,0,0,float(equity.iloc[-1]),0)
    cagr = (equity.iloc[-1]/equity.iloc[0])**(1.0/years) - 1.0
    dr = equity.pct_change().dropna()
    vol = float(dr.std()*np.sqrt(TRADING_DAYS))
    sharpe = float(dr.mean()/dr.std()*np.sqrt(TRADING_DAYS)) if dr.std()>0 else 0
    dd_c = float((equity/equity.cummax()-1).min())
    low_s = pd.Series(result.equity_intraday_low, index=result.dates).dropna()
    hi_s = pd.Series(result.equity_intraday_high, index=result.dates).dropna()
    dd_i = float((low_s/hi_s.cummax()-1).min())
    calmar = cagr/abs(dd_c) if dd_c < 0 else 0
    mr = equity.resample('ME').last().pct_change().dropna()
    ps, ns = float(mr[mr>0].sum()), float(mr[mr<0].sum())
    pf = ps/abs(ns) if ns != 0 else np.inf
    return Metrics(cagr=float(cagr),vol=vol,sharpe=sharpe,max_dd_close=dd_c,max_dd_intraday=dd_i,calmar=float(calmar),profit_factor=pf,final_equity=float(equity.iloc[-1]),years=float(years))

def pretty_metrics(m, label=''):
    return f"{label:<28s} CAGR {m.cagr*100:6.2f}%  Vol {m.vol*100:5.2f}%  Sharpe {m.sharpe:5.2f}  DDc {m.max_dd_close*100:6.2f}%  DDi {m.max_dd_intraday*100:6.2f}%  Cal {m.calmar:5.2f}  PF {m.profit_factor:5.2f}  ${m.final_equity:,.0f}"

def run_backtest(initial_capital=100000, exec_mode='close', cost_bps=5.0, impact_bps=0.0,
                leverage=1.0, margin_rate=0.0, cb_enabled=False, cb_threshold=-0.10,
                cb_cooldown_days=21, cb_reentry_mode='next_rebal', cb_peak_mode='monthly',
                sma_window=SMA_WINDOW, vol_window=VOL_WINDOW, ohlcv_data=None,
                symbols=None, start_date=None, end_date=None):
    syms = symbols or SYMBOLS
    if ohlcv_data is None: ohlcv_data = load_all_ohlcv(syms)
    open_px, high_px, low_px, close_px = build_aligned_frames(ohlcv_data)
    sma = close_px.rolling(sma_window).mean()
    vol = close_px.pct_change().rolling(vol_window).std()*np.sqrt(TRADING_DAYS)
    burn = max(sma_window, vol_window)+10
    for df_name in ['open_px','high_px','low_px','close_px','sma','vol']:
        locals()[df_name] = eval(df_name).iloc[burn:] if df_name in ('sma','vol') else eval(df_name)
    open_px=open_px.iloc[burn:]; high_px=high_px.iloc[burn:]; low_px=low_px.iloc[burn:]; close_px=close_px.iloc[burn:]
    sma=sma.reindex(close_px.index); vol=vol.reindex(close_px.index)
    if start_date: mask=close_px.index>=pd.Timestamp(start_date); open_px=open_px.loc[mask]; high_px=high_px.loc[mask]; low_px=low_px.loc[mask]; close_px=close_px.loc[mask]; sma=sma.reindex(close_px.index); vol=vol.reindex(close_px.index)
    if end_date: mask=close_px.index<=pd.Timestamp(end_date); open_px=open_px.loc[mask]; high_px=high_px.loc[mask]; low_px=low_px.loc[mask]; close_px=close_px.loc[mask]; sma=sma.reindex(close_px.index); vol=vol.reindex(close_px.index)
    dates = close_px.index; n_days = len(dates)
    rebal_set = set(); prev_month = None
    for i, d in enumerate(dates):
        ym = (d.year, d.month)
        if ym != prev_month: rebal_set.add(i); prev_month = ym
    tc = (cost_bps+impact_bps)/10000.0
    shares = {s: 0.0 for s in syms}; cash = float(initial_capital)
    eq_arr = np.zeros(n_days); hi_arr = np.zeros(n_days); lo_arr = np.zeros(n_days)
    cash_arr = np.zeros(n_days); incash = np.zeros(n_days, dtype=bool)
    cb_mode = False; cb_trig_day = -1; cb_events = []
    peak = float(initial_capital)
    qqq_c = close_px['QQQ'].values if 'QQQ' in close_px.columns else None
    for i in range(n_days):
        d = dates[i]; is_rebal = i in rebal_set
        cv = cash+sum(shares[s]*close_px.iloc[i][s] for s in syms)
        hv = cash+sum(shares[s]*high_px.iloc[i][s] for s in syms)
        lv = cash+sum(shares[s]*low_px.iloc[i][s] for s in syms)
        if is_rebal and cb_peak_mode=='monthly' and not cb_mode: peak=cv
        if cv>peak: peak=cv
        if hv>peak: peak=hv
        if cb_enabled and not cb_mode and peak>0:
            idd = lv/peak-1.0
            if idd<=cb_threshold:
                for s in syms:
                    if shares[s]!=0: cash+=shares[s]*close_px.iloc[i][s]-abs(shares[s]*close_px.iloc[i][s])*tc; shares[s]=0.0
                cb_mode=True; cb_trig_day=i; cv=cash; hv=cash; lv=cash
                ev=CBEvent(date=d,portfolio_value=cv,peak_value=peak,drawdown_pct=idd,trigger_date=d,trigger_dd=idd)
                if qqq_c is not None:
                    qn=qqq_c[i]
                    if i+1<n_days and qn>0: ev.qqq_fwd_1d=qqq_c[min(i+1,n_days-1)]/qn-1
                    if i+5<n_days and qn>0: ev.qqq_fwd_5d=qqq_c[min(i+5,n_days-1)]/qn-1
                    if i+21<n_days and qn>0: ev.qqq_fwd_21d=qqq_c[min(i+21,n_days-1)]/qn-1; ev.fwd_21d_ret=ev.qqq_fwd_21d
                cb_events.append(ev)
        if cb_enabled and cb_mode:
            ds=i-cb_trig_day; reenter=False
            if cb_reentry_mode=='next_rebal': reenter=is_rebal and ds>0
            elif cb_reentry_mode=='immediate': reenter=ds>=cb_cooldown_days
            elif cb_reentry_mode=='sma_confirm':
                if ds>=cb_cooldown_days:
                    na=sum(1 for s in syms if not np.isnan(sma.iloc[i][s]) and close_px.iloc[i][s]>sma.iloc[i][s])
                    reenter=na>=2
            if reenter:
                cb_mode=False; peak=cash; is_rebal=True
                if cb_events: cb_events[-1].reentry_date=d; cb_events[-1].reentry_value=cash
        if is_rebal and not cb_mode:
            pv=cash+sum(shares[s]*close_px.iloc[i][s] for s in syms)
            w=tp_weights_on_date(d,close_px,sma,vol); wl={s:w[s]*leverage for s in syms}
            for s in syms:
                ep=get_exec_price(exec_mode,i,s,open_px,high_px,low_px,close_px)
                if ep<=0: continue
                tv=pv*wl[s]; cuv=shares[s]*ep; dv=tv-cuv; cost=abs(dv)*tc
                cash-=(dv+cost); shares[s]+=dv/ep
            cv=cash+sum(shares[s]*close_px.iloc[i][s] for s in syms)
            hv=cash+sum(shares[s]*high_px.iloc[i][s] for s in syms)
            lv=cash+sum(shares[s]*low_px.iloc[i][s] for s in syms)
            if cb_peak_mode=='monthly': peak=cv
            if cv>peak: peak=cv
        eq_arr[i]=cv; hi_arr[i]=hv; lo_arr[i]=lv; cash_arr[i]=cash; incash[i]=cb_mode
    return BacktestResult(dates=dates,equity=eq_arr,equity_intraday_high=hi_arr,equity_intraday_low=lo_arr,cash_series=cash_arr,in_cash_mode=incash,cb_events=cb_events,config={})

def summarize_cb_events(events):
    if not events: return pd.DataFrame()
    return pd.DataFrame([{'trigger_date':e.date,'dd':e.drawdown_pct,'reentry':e.reentry_date,'fwd_21d':e.qqq_fwd_21d} for e in events])
