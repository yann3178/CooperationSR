"""
decomposition.py — Décomposition de la valeur ajoutée Trend-Parity
====================================================================

4 variantes testées sur QQQ/TLT/GLD/VNQ :
  1. Equal-weight monthly rebal (25% chaque, pas de SMA)
  2. Inverse-vol monthly rebal (pas de SMA)
  3. Equal-weight + SMA filter
  4. Trend-Parity full (inv-vol + SMA) = baseline
+ QQQ buy & hold pour référence
"""
import os
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

SYMBOLS = ['QQQ', 'TLT', 'GLD', 'VNQ']
SMA_N = 150
VOL_N = 40
COST_BPS = 5
INITIAL = 100000
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data_ohlcv')


def load_ohlcv(sym):
    df = pd.read_csv(f'{DATA_DIR}/{sym}.csv', skiprows=[1, 2],
                     parse_dates=[0], index_col=0)
    df = df.rename(columns=lambda c: c.strip())
    return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)


def run_variant(close_df, ohlcv_dict, use_inv_vol=False,
                use_sma_filter=False, leverage=1.0):
    start_idx = SMA_N + 10
    px = close_df.iloc[start_idx:]
    full_sma = close_df.rolling(SMA_N).mean()
    full_vol = close_df.pct_change().rolling(VOL_N).std() * np.sqrt(252)
    rebal_set = set()
    prev_month = None
    for d in px.index:
        if d.month != prev_month:
            rebal_set.add(d)
            prev_month = d.month
    shares = {s: 0.0 for s in SYMBOLS}
    cash = float(INITIAL)
    hist = []
    for d in px.index:
        if d in rebal_set:
            sma = full_sma.loc[d]; vol = full_vol.loc[d]; cur = px.loc[d]
            raw = {}
            for s in SYMBOLS:
                active = True
                if use_sma_filter: active = cur[s] > sma[s]
                if not active or np.isnan(vol[s]): raw[s] = 0
                else: raw[s] = (1.0 / vol[s]) if use_inv_vol else 1.0
            total = sum(raw.values())
            w = {s: raw[s] / total * leverage for s in SYMBOLS} if total > 0 else {s: 0 for s in SYMBOLS}
            value = cash + sum(shares[s] * cur[s] for s in SYMBOLS)
            for s in SYMBOLS:
                target = value * w[s]; current = shares[s] * cur[s]
                delta = target - current; cost = abs(delta) * COST_BPS / 10000
                cash -= delta + cost; shares[s] += delta / cur[s]
        eq_val = cash + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)
        low_val = cash + sum(shares[s] * ohlcv_dict[s]['Low'].loc[d] for s in SYMBOLS) if d in ohlcv_dict[SYMBOLS[0]].index else eq_val
        hist.append({'date': d, 'equity': eq_val, 'equity_low': low_val})
    return pd.DataFrame(hist).set_index('date')


def metrics(df):
    eq = df['equity']; years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    rets = eq.pct_change().fillna(0); vol = rets.std() * np.sqrt(252)
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    dd_intra = ((df['equity_low'] - eq.cummax()) / eq.cummax()).min() if 'equity_low' in df else dd
    calmar = cagr / abs(dd) if dd < 0 else 0
    ann = rets.resample('YE').sum(); worst = ann.min()
    worst_yr = ann.idxmin().year if len(ann) > 0 else 0
    mret = rets.resample('ME').sum(); pos = mret[mret > 0].sum(); neg = mret[mret < 0].sum()
    pf = abs(pos / neg) if neg != 0 else 0
    return {'cagr': round(cagr*100, 2), 'vol': round(vol*100, 2), 'sharpe': round(sharpe, 2),
            'max_dd_close': round(dd*100, 2), 'max_dd_intraday': round(dd_intra*100, 2),
            'calmar': round(calmar, 2), 'pf': round(pf, 2),
            'worst_year': round(worst*100, 2), 'worst_year_yr': worst_yr}


if __name__ == '__main__':
    print("Loading OHLCV data...")
    ohlcv = {s: load_ohlcv(s) for s in SYMBOLS}
    close_df = pd.concat({s: ohlcv[s]['Close'] for s in SYMBOLS}, axis=1).dropna()
    print(f"Common: {close_df.index[0].date()} -> {close_df.index[-1].date()}")
    qqq = close_df['QQQ'].iloc[SMA_N + 10:]
    qqq_eq = qqq / qqq.iloc[0] * INITIAL
    qqq_low = ohlcv['QQQ']['Low'].loc[qqq.index] / ohlcv['QQQ']['Close'].loc[qqq.index[0]] * INITIAL
    qqq_df = pd.DataFrame({'equity': qqq_eq, 'equity_low': qqq_low})
    m0 = metrics(qqq_df)
    results = {'(0) QQQ Buy & Hold': m0}
    for name, iv, sma in [('(1) EW+rebal', False, False), ('(2) InvVol', True, False),
                           ('(3) EW+SMA', False, True), ('(4) TP full', True, True)]:
        df = run_variant(close_df, ohlcv, use_inv_vol=iv, use_sma_filter=sma)
        results[name] = metrics(df)
    print(f"\n  {'Variante':<25s} {'CAGR':>7s} {'DD c2c':>8s} {'Sharpe':>7s} {'Calmar':>7s}")
    for name in results:
        m = results[name]
        print(f"  {name:<25s} {m['cagr']:>6.2f}% {m['max_dd_close']:>7.2f}% {m['sharpe']:>7.2f} {m['calmar']:>7.2f}")
    m1,m2,m3,m4 = results['(1) EW+rebal'],results['(2) InvVol'],results['(3) EW+SMA'],results['(4) TP full']
    print(f"\n  DECOMPOSITION vs EW+rebal:")
    for lbl,ma,mb in [("InvVol seul",m2,m1),("SMA seul",m3,m1),("Combo",m4,m1)]:
        print(f"    {lbl:<20s} CAGR {ma['cagr']-mb['cagr']:+.2f}  Sharpe {ma['sharpe']-mb['sharpe']:+.2f}  Calmar {ma['calmar']-mb['calmar']:+.2f}")
    syn = m4['sharpe'] - m2['sharpe'] - m3['sharpe'] + m1['sharpe']
    print(f"\n  Synergie Sharpe: {syn:+.3f} ({'redondance' if syn < -0.05 else 'additif'})")
