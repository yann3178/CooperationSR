"""
msci_world_comparison.py — Trend-Parity vs MSCI World / VT at equal risk
=========================================================================

Comparisons:
  1. MSCI World (URTH/VT) B&H 1.0x vs Trend-Parity 1.0x
  2. MSCI World at same DD as TP 1.5x (~-26%) → what leverage?
  3. TP at same DD as MSCI World (~-54%) → what CAGR?
"""
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from backtest_universe import download_data, trend_parity_backtest, CANDIDATES

# ─── Load data ───
print("Loading data...")
ALL = {**CANDIDATES, 'SPY': 'S&P 500', 'VT': 'Vanguard Total World',
       'URTH': 'iShares MSCI World'}
prices = download_data(list(ALL.keys()))

COMBO = ['QQQ', 'TLT', 'GLD', 'VNQ']
MARGIN = 0.055

def bh_stats(ticker, leverage=1.0, margin=0.0, start=None, end=None):
    """Buy-and-hold stats for a single ticker with optional leverage."""
    px = prices[ticker].dropna()
    if start:
        px = px.loc[start:]
    if end:
        px = px.loc[:end]
    rets = px.pct_change().fillna(0) * leverage
    if leverage > 1 and margin > 0:
        rets -= (leverage - 1) * margin / 252
    eq = (1 + rets).cumprod()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    vol = rets.std() * np.sqrt(252)
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
    calmar = cagr / abs(dd) if dd < 0 else 0
    ann = rets.resample('YE').sum()
    worst_yr = ann.min()
    worst_yr_date = ann.idxmin().year if len(ann) > 0 else 0
    return {
        'ticker': ticker, 'leverage': leverage,
        'start': px.index[0].strftime('%Y-%m-%d'),
        'end': px.index[-1].strftime('%Y-%m-%d'),
        'years': round(years, 1),
        'cagr': round(cagr * 100, 2),
        'max_dd': round(dd * 100, 2),
        'vol': round(vol * 100, 2),
        'sharpe': round(sharpe, 2),
        'calmar': round(calmar, 2),
        'worst_year': round(worst_yr * 100, 2),
        'worst_year_date': worst_yr_date,
    }

def tp_stats(leverage=1.0, margin=0.0, start=None, end=None):
    """Trend-Parity stats with optional leverage and margin cost."""
    r = trend_parity_backtest(prices, COMBO, sma_window=150, vol_window=40,
                               leverage=leverage, cost_bps=5)
    if r is None:
        return None
    if margin > 0 and leverage > 1:
        eq = r['equity_series']
        rets = eq.pct_change().fillna(0) - (leverage - 1) * margin / 252
        eq_net = (1 + rets).cumprod() * 100000
        if start:
            eq_net = eq_net.loc[start:]
        if end:
            eq_net = eq_net.loc[:end]
        years = (eq_net.index[-1] - eq_net.index[0]).days / 365.25
        cagr = (eq_net.iloc[-1] / eq_net.iloc[0]) ** (1 / years) - 1
        dd = ((eq_net - eq_net.cummax()) / eq_net.cummax()).min()
        vol = rets.std() * np.sqrt(252)
        sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
        calmar = cagr / abs(dd) if dd < 0 else 0
        ann = rets.resample('YE').sum()
        worst_yr = ann.min()
        worst_yr_date = ann.idxmin().year
        return {
            'leverage': leverage,
            'cagr': round(cagr * 100, 2),
            'max_dd': round(dd * 100, 2),
            'vol': round(vol * 100, 2),
            'sharpe': round(sharpe, 2),
            'calmar': round(calmar, 2),
            'worst_year': round(worst_yr * 100, 2),
            'worst_year_date': worst_yr_date,
        }
    else:
        eq = r['equity_series']
        if start:
            eq = eq.loc[start:]
        if end:
            eq = eq.loc[:end]
        rets = eq.pct_change().fillna(0)
        years = (eq.index[-1] - eq.index[0]).days / 365.25
        cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
        dd = ((eq - eq.cummax()) / eq.cummax()).min()
        vol = rets.std() * np.sqrt(252)
        sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
        calmar = cagr / abs(dd) if dd < 0 else 0
        ann = rets.resample('YE').sum()
        worst_yr = ann.min()
        worst_yr_date = ann.idxmin().year
        return {
            'leverage': leverage,
            'cagr': round(cagr * 100, 2),
            'max_dd': round(dd * 100, 2),
            'vol': round(vol * 100, 2),
            'sharpe': round(sharpe, 2),
            'calmar': round(calmar, 2),
            'worst_year': round(worst_yr * 100, 2),
            'worst_year_date': worst_yr_date,
        }


def fmt(r, label=''):
    return (f"  {label:<35s} CAGR {r['cagr']:5.1f}%  DD {r['max_dd']:6.1f}%  "
            f"Vol {r['vol']:5.1f}%  Sharpe {r['sharpe']:.2f}  "
            f"Calmar {r['calmar']:.2f}  WorstYr {r['worst_year']:.1f}% "
            f"({r.get('worst_year_date','')})")

# ─── Determine common window ───
# VT starts 2008-06, URTH starts 2012-01
# Use VT window (longest MSCI World proxy): 2008-07 → 2026-04
VT_START = "2008-07-01"
URTH_START = "2012-02-01"

# ═══════════════════════════════════════════════════════════
# 1. Full-period comparison (VT window: 2008-07 → 2026-04)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*90)
print("1. FULL-PERIOD COMPARISON (VT window: 2008-07 → 2026-04)")
print("="*90)

for label, fn in [
    ("VT (Total World) B&H 1.0x",   lambda: bh_stats('VT', 1.0, 0, VT_START)),
    ("URTH (MSCI World) B&H 1.0x",  lambda: bh_stats('URTH', 1.0, 0, URTH_START)),
    ("SPY B&H 1.0x",                lambda: bh_stats('SPY', 1.0, 0, VT_START)),
    ("QQQ B&H 1.0x",                lambda: bh_stats('QQQ', 1.0, 0, VT_START)),
    ("Trend-Parity 1.0x",           lambda: tp_stats(1.0, 0, VT_START)),
    ("Trend-Parity 1.2x (net)",     lambda: tp_stats(1.2, MARGIN, VT_START)),
    ("Trend-Parity 1.5x (net)",     lambda: tp_stats(1.5, MARGIN, VT_START)),
]:
    r = fn()
    if r:
        print(fmt(r, label))

# Also on URTH window (shorter, 2012+)
print(f"\n── On URTH window: {URTH_START} → 2026-04 ──")
for label, fn in [
    ("URTH B&H 1.0x",               lambda: bh_stats('URTH', 1.0, 0, URTH_START)),
    ("VT B&H 1.0x",                 lambda: bh_stats('VT', 1.0, 0, URTH_START)),
    ("SPY B&H 1.0x",                lambda: bh_stats('SPY', 1.0, 0, URTH_START)),
    ("Trend-Parity 1.0x",           lambda: tp_stats(1.0, 0, URTH_START)),
    ("Trend-Parity 1.5x (net)",     lambda: tp_stats(1.5, MARGIN, URTH_START)),
]:
    r = fn()
    if r:
        print(fmt(r, label))

# ═══════════════════════════════════════════════════════════
# 2. Equal-risk comparisons (VT window)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*90)
print("2. EQUAL-RISK COMPARISONS (VT window)")
print("="*90)

# First, get reference DDs
tp10 = tp_stats(1.0, 0, VT_START)
tp15 = tp_stats(1.5, MARGIN, VT_START)
vt10 = bh_stats('VT', 1.0, 0, VT_START)

print(f"\n  Reference drawdowns:")
print(f"    TP 1.0x MaxDD  = {tp10['max_dd']:.1f}%")
print(f"    TP 1.5x MaxDD  = {tp15['max_dd']:.1f}%")
print(f"    VT 1.0x MaxDD  = {vt10['max_dd']:.1f}%")

# 2a. MSCI World at same DD as TP 1.5x
# VT at 1.0x has DD ~ -54%. We need DD ~ -26% (TP 1.5x DD).
# Since DD scales ~linearly with leverage for B&H:
# target_lev = target_DD / DD_1x
target_dd_tp15 = abs(tp15['max_dd'])
vt_dd_1x = abs(vt10['max_dd'])
lev_vt_match_tp15 = target_dd_tp15 / vt_dd_1x

print(f"\n── 2a. VT at same DD as TP 1.5x (DD ≈ {tp15['max_dd']:.1f}%) ──")
print(f"  Estimated VT leverage: {lev_vt_match_tp15:.2f}x")

# Scan VT leverages to find the one matching TP 1.5x DD
print(f"\n  VT leverage scan:")
best_match = None
for lev_100 in range(10, 120, 2):  # 0.10 to 1.18
    lev = lev_100 / 100.0
    r = bh_stats('VT', lev, MARGIN if lev > 1 else 0, VT_START)
    if r:
        if best_match is None or abs(r['max_dd'] - tp15['max_dd']) < abs(best_match['max_dd'] - tp15['max_dd']):
            best_match = r
        if lev_100 % 10 == 0 or abs(r['max_dd'] - tp15['max_dd']) < 2:
            print(f"    lev={lev:.2f}  CAGR {r['cagr']:5.1f}%  DD {r['max_dd']:6.1f}%")

print(f"\n  Best VT match for DD ≈ {tp15['max_dd']:.1f}%:")
print(fmt(best_match, f"VT @ {best_match['leverage']:.2f}x"))
print(fmt(tp15, "TP 1.5x (net margin)"))
print(f"\n  → À risque égal (DD ≈ {tp15['max_dd']:.0f}%), "
      f"TP gagne {tp15['cagr'] - best_match['cagr']:.1f} pp de CAGR")

# 2b. TP at same DD as VT 1.0x
print(f"\n── 2b. TP at same DD as VT 1.0x (DD ≈ {vt10['max_dd']:.1f}%) ──")
best_tp = None
print(f"\n  TP leverage scan:")
for lev_10 in range(10, 50):  # 1.0 to 4.9
    lev = lev_10 / 10.0
    r = tp_stats(lev, MARGIN, VT_START)
    if r:
        if best_tp is None or abs(r['max_dd'] - vt10['max_dd']) < abs(best_tp['max_dd'] - vt10['max_dd']):
            best_tp = r
        if lev_10 % 5 == 0 or abs(r['max_dd'] - vt10['max_dd']) < 3:
            print(f"    lev={lev:.1f}  CAGR {r['cagr']:5.1f}%  DD {r['max_dd']:6.1f}%")

print(f"\n  Best TP match for DD ≈ {vt10['max_dd']:.1f}%:")
print(fmt(best_tp, f"TP @ {best_tp['leverage']:.1f}x (net margin)"))
print(fmt(vt10, "VT B&H 1.0x"))
print(f"\n  → À risque égal (DD ≈ {vt10['max_dd']:.0f}%), "
      f"TP gagne {best_tp['cagr'] - vt10['cagr']:.1f} pp de CAGR")

# 2c. Same comparison but TP 1.0x vs VT at same DD
print(f"\n── 2c. VT at same DD as TP 1.0x (DD ≈ {tp10['max_dd']:.1f}%) ──")
best_vt2 = None
for lev_100 in range(10, 80, 2):
    lev = lev_100 / 100.0
    r = bh_stats('VT', lev, MARGIN if lev > 1 else 0, VT_START)
    if r:
        if best_vt2 is None or abs(r['max_dd'] - tp10['max_dd']) < abs(best_vt2['max_dd'] - tp10['max_dd']):
            best_vt2 = r

print(f"  Best VT match for DD ≈ {tp10['max_dd']:.1f}%:")
print(fmt(best_vt2, f"VT @ {best_vt2['leverage']:.2f}x"))
print(fmt(tp10, "TP 1.0x"))
print(f"\n  → À risque égal (DD ≈ {tp10['max_dd']:.0f}%), "
      f"TP gagne {tp10['cagr'] - best_vt2['cagr']:.1f} pp de CAGR")

# ═══════════════════════════════════════════════════════════
# 3. Summary table
# ═══════════════════════════════════════════════════════════
print("\n" + "="*90)
print("3. SUMMARY — EQUAL-RISK COMPARISON TABLE")
print("="*90)
print(f"\n  {'Comparison':<45s} {'CAGR':>6s} {'MaxDD':>7s} {'Sharpe':>7s} {'Calmar':>7s}")
print("  " + "-"*75)
for label, r in [
    ("VT B&H 1.0x",                        vt10),
    (f"VT @ {best_vt2['leverage']:.2f}x (DD≈TP 1.0x)", best_vt2),
    ("Trend-Parity 1.0x",                  tp10),
    ("",                                    None),
    (f"VT @ {best_match['leverage']:.2f}x (DD≈TP 1.5x)", best_match),
    ("Trend-Parity 1.5x (net margin)",      tp15),
    ("",                                    None),
    ("VT B&H 1.0x (reference)",             vt10),
    (f"TP @ {best_tp['leverage']:.1f}x (DD≈VT 1.0x, net)", best_tp),
]:
    if r is None:
        print()
        continue
    print(f"  {label:<45s} {r['cagr']:5.1f}% {r['max_dd']:6.1f}% "
          f"{r['sharpe']:6.2f} {r['calmar']:6.2f}")

print("\n" + "="*90)
print("  DONE")
print("="*90)
