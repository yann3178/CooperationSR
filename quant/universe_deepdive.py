"""
Deep-dive on the top combos from the universe explorer:
  1. GLD/IEF/QQQ/VNQ  (best balanced: Sharpe 1.13, Calmar 0.68)
  2. GLD/QQQ/TLT/VNQ  (highest Calmar 0.76, CAGR 12.5%)
  3. GLD/IEF/QQQ/TIP/VNQ (best Sharpe 1.16)
  4. GLD/IEF/LQD/QQQ/TIP/VNQ (best Sharpe 1.19)

Tests:
  - SMA robustness (100, 120, 150, 175, 200)
  - Leverage 1.0 vs 1.2
  - Correlation matrix
  - Year-by-year performance
  - Worst drawdown periods
"""
import numpy as np
import pandas as pd
from backtest_universe import download_data, trend_parity_backtest, CANDIDATES

# Download data once
prices = download_data(list(CANDIDATES.keys()))

COMBOS = {
    "BASELINE (QQQ/IEF/GLD)":      ["QQQ", "IEF", "GLD"],
    "A: QQQ/IEF/GLD/VNQ":          ["QQQ", "IEF", "GLD", "VNQ"],
    "B: QQQ/TLT/GLD/VNQ":          ["QQQ", "TLT", "GLD", "VNQ"],
    "C: QQQ/IEF/GLD/TIP/VNQ":      ["QQQ", "IEF", "GLD", "TIP", "VNQ"],
    "D: QQQ/IEF/GLD/LQD/TIP/VNQ":  ["QQQ", "IEF", "GLD", "LQD", "TIP", "VNQ"],
}

# ─── 1. SMA robustness ───
print("\n" + "="*80)
print("1. SMA ROBUSTNESS")
print("="*80)
for sma in [100, 120, 150, 175, 200]:
    print(f"\n── SMA = {sma} ──")
    for name, syms in COMBOS.items():
        r = trend_parity_backtest(prices, syms, sma_window=sma)
        if r:
            print(f"  {name:<35s} CAGR {r['cagr']:5.1f}%  "
                  f"DD {r['max_dd']:6.1f}%  Sharpe {r['sharpe']:.2f}  "
                  f"Calmar {r['calmar']:.2f}")

# ─── 2. Leverage 1.2 ───
print("\n" + "="*80)
print("2. LEVERAGE 1.0 vs 1.2")
print("="*80)
for lev in [1.0, 1.2]:
    print(f"\n── Leverage = {lev} ──")
    for name, syms in COMBOS.items():
        r = trend_parity_backtest(prices, syms, leverage=lev)
        if r:
            print(f"  {name:<35s} CAGR {r['cagr']:5.1f}%  "
                  f"DD {r['max_dd']:6.1f}%  Sharpe {r['sharpe']:.2f}  "
                  f"Calmar {r['calmar']:.2f}  PF {r['profit_factor']:.1f}")

# ─── 3. Correlation matrix for top combo ───
print("\n" + "="*80)
print("3. MATRICE DE CORRÉLATION — QQQ/IEF/GLD/VNQ")
print("="*80)
px = prices[["QQQ", "IEF", "GLD", "VNQ"]].dropna()
corr = px.pct_change().corr().round(3)
print(corr.to_string())

print("\n── QQQ/TLT/GLD/VNQ ──")
px2 = prices[["QQQ", "TLT", "GLD", "VNQ"]].dropna()
corr2 = px2.pct_change().corr().round(3)
print(corr2.to_string())

# ─── 4. Year-by-year ───
print("\n" + "="*80)
print("4. YEAR-BY-YEAR PERFORMANCE — QQQ/IEF/GLD/VNQ vs BASELINE")
print("="*80)

for name, syms in [("BASELINE", ["QQQ","IEF","GLD"]),
                    ("A: +VNQ", ["QQQ","IEF","GLD","VNQ"]),
                    ("B: TLT+VNQ", ["QQQ","TLT","GLD","VNQ"])]:
    r = trend_parity_backtest(prices, syms)
    if r and 'equity_series' in r:
        eq = r['equity_series']
        ann = eq.resample("YE").last().pct_change().dropna()
        print(f"\n── {name} ──")
        print(f"  {'Year':<6s} {'Return':>8s} {'Cumul':>10s}")
        cumul = 1.0
        for d, v in ann.items():
            cumul *= (1 + v)
            print(f"  {d.year:<6d} {v*100:>+7.2f}% {cumul*100-100:>+9.2f}%")
        # Worst year
        worst_yr = ann.idxmin().year
        print(f"  Worst: {worst_yr} ({ann.min()*100:+.2f}%)")
        # Count negative years
        neg = (ann < 0).sum()
        print(f"  Negative years: {neg}/{len(ann)}")
