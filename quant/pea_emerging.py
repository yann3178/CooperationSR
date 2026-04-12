"""
pea_emerging.py — Trend-Parity UCITS / PEA / Émergents Analysis
================================================================

Phases:
  1. Download & validate all candidates
  2. Correlation matrix + heatmap
  3. Combinatorial backtest (structured combos + exhaustive)
  4. Fiscal analysis PEA vs CTO
  5. EM stress tests (2008, 2013, 2018, 2020, 2022)
  6. Leverage + fiscal for top combo
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')
from itertools import combinations

from backtest_universe import download_data, trend_parity_backtest

# ═══════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════
SMA = 150; VOL = 40; LEV = 1.0; COST = 5; CAPITAL = 100000
MARGIN = 0.055; TAX_PEA = 0.172; TAX_CTO = 0.30

CANDIDATES = {
    'URTH': 'MSCI World', 'SPY': 'S&P 500', 'QQQ': 'Nasdaq 100',
    'EFA': 'MSCI EAFE',
    'INDA': 'MSCI India', 'EEM': 'MSCI EM', 'FXI': 'China 50',
    'EWZ': 'Brazil', 'EWY': 'South Korea', 'THD': 'Thailand',
    'VNM': 'Vietnam', 'EWW': 'Mexico', 'EIDO': 'Indonesia', 'TUR': 'Turkey',
    'VNQ': 'US REITs', 'VNQI': 'Intl REITs', 'RWX': 'DJ Intl RE',
    'TLT': 'US 20Y+', 'IEF': 'US 7-10Y', 'BWX': 'Intl Bond', 'EMB': 'EM Bond',
    'GLD': 'Gold', 'SLV': 'Silver', 'DBC': 'Commodities',
    'VT': 'Total World',
}

# PEA eligibility (equity-based, UCITS synthetic available)
PEA_ELIGIBLE = {'URTH','SPY','QQQ','EFA','INDA','EEM','FXI','EWZ','EWY',
                'THD','VNM','EWW','EIDO','TUR','VNQ','VNQI','RWX','VT'}

# ═══════════════════════════════════════════════════════
# PHASE 1 — Download
# ═══════════════════════════════════════════════════════
print("="*80)
print("PHASE 1 — Download & Validate")
print("="*80)
prices = download_data(list(CANDIDATES.keys()))

# Report inception dates
print(f"\n  {'Ticker':<6s} {'Start':>12s} {'End':>12s} {'Years':>6s} {'PEA':>5s}")
print("  " + "-"*50)
inception = {}
for c in sorted(prices.columns):
    s = prices[c].dropna()
    if len(s) > 0:
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        inception[c] = s.index[0]
        pea = "PEA" if c in PEA_ELIGIBLE else "CTO"
        print(f"  {c:<6s} {s.index[0].date()!s:>12s} {s.index[-1].date()!s:>12s} "
              f"{yrs:5.1f}y  {pea}")

# Filter: > 10 years
MIN_YEARS = 10
long_hist = [c for c in prices.columns
             if (prices[c].dropna().index[-1] - prices[c].dropna().index[0]).days > MIN_YEARS * 365]
print(f"\n  {len(long_hist)} tickers with > {MIN_YEARS}y history: {sorted(long_hist)}")

# ═══════════════════════════════════════════════════════
# PHASE 2 — Correlation matrix
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 2 — Correlation Matrix")
print("="*80)

# Use the longest common window
common = prices[long_hist].dropna()
corr = common.pct_change().corr()

# Heatmap
fig, ax = plt.subplots(figsize=(14, 11))
im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-0.5, vmax=1)
ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=90, fontsize=8)
ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.columns, fontsize=8)
for i in range(len(corr)):
    for j in range(len(corr)):
        ax.text(j, i, f"{corr.iloc[i,j]:.2f}", ha='center', va='center', fontsize=6,
                color='white' if abs(corr.iloc[i,j]) > 0.5 else 'black')
fig.colorbar(im, ax=ax, shrink=0.8)
ax.set_title("Correlation Matrix — All Candidates (daily returns)")
fig.tight_layout()
fig.savefig("correlation_heatmap.png", dpi=140)
print("  → Saved correlation_heatmap.png")

# Key pairs
print("\n  Key correlation pairs:")
key_pairs = [('QQQ','INDA'), ('QQQ','EEM'), ('SPY','INDA'), ('SPY','EEM'),
             ('INDA','EEM'), ('QQQ','TLT'), ('QQQ','GLD'), ('QQQ','VNQ'),
             ('INDA','TLT'), ('INDA','GLD'), ('TLT','BWX'), ('VNQ','VNQI'),
             ('INDA','VNQ'), ('EFA','QQQ'), ('EWZ','QQQ'), ('EWY','QQQ')]
for a, b in key_pairs:
    if a in corr.columns and b in corr.columns:
        print(f"    {a}/{b}: {corr.loc[a,b]:.3f}")

# ═══════════════════════════════════════════════════════
# PHASE 3 — Structured combo tests
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 3 — Structured Combo Tests")
print("="*80)

COMBOS = {
    'BASE_4':       ['QQQ', 'TLT', 'GLD', 'VNQ'],
    'INDIA_5':      ['QQQ', 'TLT', 'GLD', 'VNQ', 'INDA'],
    'EM_5':         ['QQQ', 'TLT', 'GLD', 'VNQ', 'EEM'],
    'INDIA_WORLD':  ['URTH', 'TLT', 'GLD', 'VNQ', 'INDA'],
    'GLOBAL_5':     ['URTH', 'TLT', 'GLD', 'INDA', 'VNQI'],
    'GLOBAL_6':     ['URTH', 'TLT', 'GLD', 'INDA', 'VNQ', 'EFA'],
    'PEA_MAX':      ['URTH', 'INDA', 'VNQ', 'TLT', 'GLD'],
    'PEA_QQQ':      ['QQQ', 'INDA', 'VNQ', 'TLT', 'GLD'],
    'NO_US':        ['EFA', 'INDA', 'BWX', 'GLD', 'VNQI'],
    'EM_HEAVY':     ['QQQ', 'INDA', 'EEM', 'GLD', 'TLT'],
    'LATAM':        ['QQQ', 'TLT', 'GLD', 'EWZ', 'EWW'],
    'SPY_INDIA':    ['SPY', 'TLT', 'GLD', 'VNQ', 'INDA'],
    'SPY_GLOBAL':   ['SPY', 'TLT', 'GLD', 'VNQI', 'INDA'],
    'KOREA_5':      ['QQQ', 'TLT', 'GLD', 'VNQ', 'EWY'],
    'INDIA_NOVREIT':['QQQ', 'TLT', 'GLD', 'INDA'],
    'SPY_EEM':      ['SPY', 'TLT', 'GLD', 'VNQ', 'EEM'],
}

print(f"\n  {'Combo':<20s} {'CAGR':>6s} {'MaxDD':>7s} {'Sharpe':>7s} {'Calmar':>7s} "
      f"{'PF':>5s} {'WorstYr':>8s} {'Corr':>5s} {'Yrs':>5s}")
print("  " + "-"*80)

combo_results = {}
for name, syms in COMBOS.items():
    # Check all symbols available
    avail = [s for s in syms if s in prices.columns]
    if len(avail) < len(syms):
        missing = set(syms) - set(avail)
        print(f"  {name:<20s} SKIP (missing {missing})")
        continue
    r = trend_parity_backtest(prices, syms, sma_window=SMA, vol_window=VOL,
                               leverage=LEV, cost_bps=COST)
    if r:
        combo_results[name] = r
        pea_pct = sum(1 for s in syms if s in PEA_ELIGIBLE) / len(syms) * 100
        print(f"  {name:<20s} {r['cagr']:5.1f}% {r['max_dd']:6.1f}% "
              f"{r['sharpe']:6.2f} {r['calmar']:6.2f} {r['profit_factor']:4.1f} "
              f"{r['worst_year']:7.1f}% {r['avg_correlation']:4.2f} "
              f"{r['years']:4.1f}y  PEA:{pea_pct:.0f}%")
    else:
        print(f"  {name:<20s} SKIP (insufficient data)")

# ── Exhaustive combos on long-history subset ──
print("\n  ── Exhaustive search (4-5 assets, >12y history) ──")
# Must include at least 1 hedge (TLT/IEF/BWX/GLD) and 1 equity
HEDGES = {'TLT','IEF','BWX','GLD','SLV','DBC','EMB'}
EQUITIES = set(long_hist) - HEDGES

exhaust_results = []
for n in [4, 5]:
    for combo in combinations(sorted(long_hist), n):
        combo = list(combo)
        has_hedge = any(c in HEDGES for c in combo)
        has_equity = any(c in EQUITIES for c in combo)
        if not (has_hedge and has_equity):
            continue
        r = trend_parity_backtest(prices, combo, sma_window=SMA,
                                   vol_window=VOL, leverage=LEV, cost_bps=COST)
        if r and r['years'] > 10:
            r['pea_pct'] = sum(1 for s in combo if s in PEA_ELIGIBLE) / len(combo)
            exhaust_results.append(r)

edf = pd.DataFrame(exhaust_results)
print(f"  {len(edf)} valid combos tested")

if not edf.empty:
    print(f"\n  Top 10 by Sharpe (exhaustive, >10y):")
    for _, row in edf.nlargest(10, 'sharpe').iterrows():
        print(f"    Sharpe {row['sharpe']:.2f} | CAGR {row['cagr']:5.1f}% | "
              f"DD {row['max_dd']:6.1f}% | Calmar {row['calmar']:.2f} | "
              f"PEA {row['pea_pct']*100:.0f}% | {row['symbols']}")

    print(f"\n  Top 10 by Calmar (exhaustive, >10y):")
    for _, row in edf.nlargest(10, 'calmar').iterrows():
        print(f"    Calmar {row['calmar']:.2f} | CAGR {row['cagr']:5.1f}% | "
              f"DD {row['max_dd']:6.1f}% | Sharpe {row['sharpe']:.2f} | "
              f"{row['symbols']}")

    # Combos with INDA
    inda_df = edf[edf['symbols'].str.contains('INDA')]
    if not inda_df.empty:
        print(f"\n  Top 5 with INDA:")
        for _, row in inda_df.nlargest(5, 'sharpe').iterrows():
            print(f"    Sharpe {row['sharpe']:.2f} | CAGR {row['cagr']:5.1f}% | "
                  f"DD {row['max_dd']:6.1f}% | {row['symbols']}")

# ═══════════════════════════════════════════════════════
# PHASE 4 — Fiscal analysis
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 4 — Fiscal Analysis PEA/CTO")
print("="*80)

def cagr_net_fiscal(cagr_brut, pct_pea):
    tax = pct_pea * TAX_PEA + (1 - pct_pea) * TAX_CTO
    return cagr_brut * (1 - tax)

# Top combos for fiscal comparison
fiscal_combos = ['BASE_4', 'INDIA_5', 'PEA_QQQ', 'SPY_INDIA', 'EM_5']
print(f"\n  {'Combo':<20s} {'CAGR':>6s} {'%PEA':>5s} {'Tax%':>5s} "
      f"{'CAGR_net':>8s} {'vs 100%CTO':>10s}")
print("  " + "-"*65)
for name in fiscal_combos:
    if name not in combo_results:
        continue
    r = combo_results[name]
    syms = COMBOS[name]
    pea_pct = sum(1 for s in syms if s in PEA_ELIGIBLE) / len(syms)
    cagr_b = r['cagr'] / 100
    cagr_pea = cagr_net_fiscal(cagr_b, pea_pct) * 100
    cagr_cto = cagr_net_fiscal(cagr_b, 0.0) * 100
    tax_avg = pea_pct * TAX_PEA + (1-pea_pct) * TAX_CTO
    gain = cagr_pea - cagr_cto
    print(f"  {name:<20s} {r['cagr']:5.1f}% {pea_pct*100:4.0f}% "
          f"{tax_avg*100:4.1f}% {cagr_pea:7.2f}% {gain:+9.2f}%")

# ═══════════════════════════════════════════════════════
# PHASE 5 — EM stress tests
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 5 — Emerging Market Stress Tests")
print("="*80)

em_tickers = ['INDA', 'EEM', 'FXI', 'EWZ', 'EWY']
crises = [
    ("GFC 2008",         "2008-01-01", "2008-12-31"),
    ("Taper 2013",       "2013-05-01", "2013-12-31"),
    ("EM crisis 2018",   "2018-01-01", "2018-12-31"),
    ("COVID 2020",       "2020-01-01", "2020-06-30"),
    ("USD rally 2022",   "2022-01-01", "2022-12-31"),
]

for crisis_name, start, end in crises:
    print(f"\n  ── {crisis_name} ({start} → {end}) ──")
    for tk in em_tickers:
        px = prices[tk].dropna()
        sub = px.loc[start:end]
        if len(sub) < 20:
            continue
        ret = sub.iloc[-1] / sub.iloc[0] - 1
        dd = ((sub - sub.cummax()) / sub.cummax()).min()
        sma150 = px.rolling(150).mean()
        sma_sub = sma150.loc[start:end]
        on_pct = (sub > sma_sub).mean() * 100
        # Was SMA ON at start of crisis?
        start_on = "ON" if sub.iloc[0] > sma_sub.iloc[0] else "OFF"
        # Was SMA ON at end?
        end_on = "ON" if sub.iloc[-1] > sma_sub.iloc[-1] else "OFF"
        print(f"    {tk:<5s} Return {ret*100:+6.1f}%  DD {dd*100:6.1f}%  "
              f"SMA: {start_on}→{end_on}  ON {on_pct:4.0f}% of time")

# Combo stress: INDIA_5 vs BASE_4 in each crisis
print(f"\n  ── Strategy-level: INDIA_5 vs BASE_4 per crisis ──")
for crisis_name, start, end in crises:
    print(f"\n  {crisis_name}:")
    for name in ['BASE_4', 'INDIA_5', 'EM_5']:
        syms = COMBOS[name]
        r = trend_parity_backtest(prices, syms, sma_window=SMA,
                                   vol_window=VOL, leverage=LEV, cost_bps=COST)
        if r and 'equity_series' in r:
            eq = r['equity_series']
            sub = eq.loc[start:end]
            if len(sub) > 5:
                ret = sub.iloc[-1] / sub.iloc[0] - 1
                dd = ((sub - sub.cummax()) / sub.cummax()).min()
                print(f"    {name:<15s} Return {ret*100:+6.1f}%  DD {dd*100:6.1f}%")

# ═══════════════════════════════════════════════════════
# PHASE 6 — Leverage + fiscal for top combo
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 6 — Leverage + Fiscal for Top Combos")
print("="*80)

for combo_name in ['BASE_4', 'INDIA_5', 'PEA_QQQ']:
    syms = COMBOS[combo_name]
    pea_pct = sum(1 for s in syms if s in PEA_ELIGIBLE) / len(syms)
    print(f"\n  ── {combo_name} (PEA {pea_pct*100:.0f}%) ──")
    print(f"  {'Lev':>4s} {'CAGR_gross':>10s} {'CAGR_net':>9s} {'CAGR_fiscal':>11s} "
          f"{'MaxDD':>7s} {'Sharpe':>7s}")
    print("  " + "-"*55)
    for lev in [1.0, 1.1, 1.2, 1.3, 1.5, 1.7, 2.0]:
        r = trend_parity_backtest(prices, syms, sma_window=SMA, vol_window=VOL,
                                   leverage=lev, cost_bps=COST)
        if r:
            cagr_g = r['cagr']
            # Net of margin
            if lev > 1:
                margin_drag = (lev - 1) * MARGIN * 100
                cagr_n = cagr_g - margin_drag
            else:
                cagr_n = cagr_g
            # Net of tax
            cagr_f = cagr_net_fiscal(cagr_n / 100, pea_pct) * 100
            print(f"  {lev:4.1f} {cagr_g:9.1f}% {cagr_n:8.1f}% {cagr_f:10.1f}% "
                  f"{r['max_dd']:6.1f}% {r['sharpe']:6.2f}")

print("\n" + "="*80)
print("  ALL PHASES COMPLETE")
print("="*80)
