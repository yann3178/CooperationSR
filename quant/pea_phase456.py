"""Phases 4-6 only — using structured combo results from pea_emerging.py."""
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from backtest_universe import download_data, trend_parity_backtest

SMA = 150; VOL = 40; LEV = 1.0; COST = 5; CAPITAL = 100000
MARGIN = 0.055; TAX_PEA = 0.172; TAX_CTO = 0.30

CANDIDATES = {
    'URTH': 'MSCI World', 'SPY': 'S&P 500', 'QQQ': 'Nasdaq 100',
    'EFA': 'MSCI EAFE', 'INDA': 'MSCI India', 'EEM': 'MSCI EM',
    'FXI': 'China 50', 'EWZ': 'Brazil', 'EWY': 'South Korea',
    'VNQ': 'US REITs', 'VNQI': 'Intl REITs',
    'TLT': 'US 20Y+', 'IEF': 'US 7-10Y', 'BWX': 'Intl Bond',
    'GLD': 'Gold', 'SLV': 'Silver', 'DBC': 'Commodities', 'VT': 'Total World',
}

PEA_ELIGIBLE = {'URTH','SPY','QQQ','EFA','INDA','EEM','FXI','EWZ','EWY',
                'VNQ','VNQI','VT'}

print("Loading data...")
prices = download_data(list(CANDIDATES.keys()))

COMBOS = {
    'BASE_4':       ['QQQ', 'TLT', 'GLD', 'VNQ'],
    'EM_5':         ['QQQ', 'TLT', 'GLD', 'VNQ', 'EEM'],
    'KOREA_5':      ['QQQ', 'TLT', 'GLD', 'VNQ', 'EWY'],
    'INDIA_5':      ['QQQ', 'TLT', 'GLD', 'VNQ', 'INDA'],
    'PEA_QQQ':      ['QQQ', 'INDA', 'VNQ', 'TLT', 'GLD'],
    'INDIA_NOVREIT':['QQQ', 'TLT', 'GLD', 'INDA'],
    'SPY_EEM':      ['SPY', 'TLT', 'GLD', 'VNQ', 'EEM'],
    'EM_HEAVY':     ['QQQ', 'INDA', 'EEM', 'GLD', 'TLT'],
}

def cagr_net_fiscal(cagr_brut, pct_pea):
    tax = pct_pea * TAX_PEA + (1 - pct_pea) * TAX_CTO
    return cagr_brut * (1 - tax)

# ═══════════════════════════════════════════════════════
# PHASE 4 — Fiscal analysis
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 4 — Fiscal Analysis PEA/CTO")
print("="*80)

print(f"\n  {'Combo':<18s} {'CAGR':>6s} {'#PEA/#Tot':>9s} {'%PEA':>5s} "
      f"{'AvgTax':>6s} {'CAGR_net':>9s} {'vs100%CTO':>9s} {'PEA_assets':>30s}")
print("  " + "-"*100)
for name, syms in COMBOS.items():
    r = trend_parity_backtest(prices, syms, sma_window=SMA, vol_window=VOL,
                               leverage=LEV, cost_bps=COST)
    if not r:
        continue
    pea_assets = [s for s in syms if s in PEA_ELIGIBLE]
    cto_assets = [s for s in syms if s not in PEA_ELIGIBLE]
    pea_pct = len(pea_assets) / len(syms)
    cagr_b = r['cagr'] / 100
    cagr_net = cagr_net_fiscal(cagr_b, pea_pct) * 100
    cagr_cto = cagr_net_fiscal(cagr_b, 0.0) * 100
    tax_avg = pea_pct * TAX_PEA + (1-pea_pct) * TAX_CTO
    gain = cagr_net - cagr_cto
    print(f"  {name:<18s} {r['cagr']:5.1f}% {len(pea_assets)}/{len(syms)}  "
          f"{pea_pct*100:4.0f}% {tax_avg*100:5.1f}% {cagr_net:8.2f}% "
          f"{gain:+8.2f}%  PEA:{','.join(pea_assets)} | CTO:{','.join(cto_assets)}")

# Dollar gain over 20 years on 100k
print(f"\n  Gain PEA vs 100% CTO sur $100k sur 20 ans:")
for name, syms in [('BASE_4', COMBOS['BASE_4']),
                    ('EM_5', COMBOS['EM_5']),
                    ('KOREA_5', COMBOS['KOREA_5'])]:
    r = trend_parity_backtest(prices, syms, sma_window=SMA, vol_window=VOL,
                               leverage=LEV, cost_bps=COST)
    if not r: continue
    pea_pct = sum(1 for s in syms if s in PEA_ELIGIBLE) / len(syms)
    c = r['cagr'] / 100
    final_pea = CAPITAL * (1 + cagr_net_fiscal(c, pea_pct)) ** 20
    final_cto = CAPITAL * (1 + cagr_net_fiscal(c, 0)) ** 20
    print(f"  {name:<18s}: PEA/CTO ${final_pea:,.0f} vs 100%CTO ${final_cto:,.0f} "
          f"→ gain PEA: ${final_pea - final_cto:,.0f}")

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
    print(f"\n  ── {crisis_name} ──")
    for tk in em_tickers:
        if tk not in prices.columns:
            continue
        px = prices[tk].dropna()
        sub = px.loc[start:end]
        if len(sub) < 20:
            print(f"    {tk:<5s} N/A (no data)")
            continue
        ret = sub.iloc[-1] / sub.iloc[0] - 1
        dd = ((sub - sub.cummax()) / sub.cummax()).min()
        sma150 = px.rolling(150).mean()
        sma_sub = sma150.loc[start:end].dropna()
        sub_al = sub.loc[sma_sub.index]
        if len(sub_al) > 0 and len(sma_sub) > 0:
            on_pct = (sub_al > sma_sub).mean() * 100
            start_on = "ON" if sub_al.iloc[0] > sma_sub.iloc[0] else "OFF"
            end_on = "ON" if sub_al.iloc[-1] > sma_sub.iloc[-1] else "OFF"
        else:
            on_pct = 0; start_on = "?"; end_on = "?"
        print(f"    {tk:<5s} Return {ret*100:+6.1f}%  DD {dd*100:6.1f}%  "
              f"SMA: {start_on}→{end_on}  ON {on_pct:4.0f}% of time")

# Strategy-level comparison in each crisis
print(f"\n  ── Strategy-level performance in crises ──")
test_combos = ['BASE_4', 'EM_5', 'KOREA_5', 'INDIA_5']
for crisis_name, start, end in crises:
    print(f"\n  {crisis_name}:")
    for name in test_combos:
        syms = COMBOS[name]
        r = trend_parity_backtest(prices, syms, sma_window=SMA,
                                   vol_window=VOL, leverage=LEV, cost_bps=COST)
        if r and 'equity_series' in r:
            eq = r['equity_series']
            sub = eq.loc[start:end]
            if len(sub) > 5:
                ret = sub.iloc[-1] / sub.iloc[0] - 1
                dd = ((sub - sub.cummax()) / sub.cummax()).min()
                print(f"    {name:<18s} Return {ret*100:+6.1f}%  DD {dd*100:6.1f}%")

# ═══════════════════════════════════════════════════════
# PHASE 6 — Leverage + fiscal
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 6 — Leverage + Fiscal for Top Combos")
print("="*80)

for combo_name in ['BASE_4', 'EM_5', 'KOREA_5']:
    syms = COMBOS[combo_name]
    pea_pct = sum(1 for s in syms if s in PEA_ELIGIBLE) / len(syms)
    print(f"\n  ── {combo_name} (PEA {pea_pct*100:.0f}%) ──")
    print(f"  {'Lev':>4s} {'CAGR_gross':>10s} {'CAGR_margin':>11s} "
          f"{'CAGR_fiscal':>11s} {'MaxDD':>7s} {'Sharpe':>7s} {'Calmar':>7s}")
    print("  " + "-"*65)
    for lev in [1.0, 1.1, 1.2, 1.3, 1.5, 1.7, 2.0]:
        r = trend_parity_backtest(prices, syms, sma_window=SMA, vol_window=VOL,
                                   leverage=lev, cost_bps=COST)
        if r:
            cagr_g = r['cagr']
            margin_drag = (lev - 1) * MARGIN * 100 if lev > 1 else 0
            cagr_m = cagr_g - margin_drag
            cagr_f = cagr_net_fiscal(cagr_m / 100, pea_pct) * 100
            # Approximate DD with margin
            dd_approx = r['max_dd'] * (1 + (lev-1)*0.1) if lev > 1 else r['max_dd']
            print(f"  {lev:4.1f} {cagr_g:9.1f}% {cagr_m:10.1f}% "
                  f"{cagr_f:10.1f}% {r['max_dd']:6.1f}% "
                  f"{r['sharpe']:6.2f} {r['calmar']:6.2f}")

# Final comparison: all strategies at lev 1.0, net of fiscal
print(f"\n  ── Final: all combos at lev 1.0, CAGR net fiscal ──")
print(f"  {'Combo':<18s} {'CAGR':>6s} {'MaxDD':>7s} {'Sharpe':>7s} "
      f"{'CAGR_net':>9s} {'Yrs':>5s}")
print("  " + "-"*55)
for name, syms in COMBOS.items():
    r = trend_parity_backtest(prices, syms, sma_window=SMA, vol_window=VOL,
                               leverage=LEV, cost_bps=COST)
    if not r: continue
    pea_pct = sum(1 for s in syms if s in PEA_ELIGIBLE) / len(syms)
    cagr_f = cagr_net_fiscal(r['cagr'] / 100, pea_pct) * 100
    print(f"  {name:<18s} {r['cagr']:5.1f}% {r['max_dd']:6.1f}% "
          f"{r['sharpe']:6.2f} {cagr_f:8.2f}% {r['years']:4.1f}y")

print("\n" + "="*80)
print("  ALL PHASES COMPLETE")
print("="*80)
