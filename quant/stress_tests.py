"""
stress_tests.py — Trend-Parity Bias & Robustness Analysis
==========================================================

6 tests to determine whether the strategy's performance is structural
or a product of historical selection bias.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import warnings
warnings.filterwarnings('ignore')

from backtest_universe import download_data, trend_parity_backtest, CANDIDATES

# ─── Data ────────────────────────────────────────────────
print("Loading data...")
EXTRA = {'SPY': 'S&P 500'}
ALL_SYMS = {**CANDIDATES, **EXTRA}
prices = download_data(list(ALL_SYMS.keys()))

SMA = 150
VOL = 40
LEV = 1.0
COST = 5

def bt(syms, sma=SMA, start=None, end=None):
    px = prices[list(syms)].dropna()
    if start:
        px = px.loc[start:]
    if end:
        px = px.loc[:end]
    return trend_parity_backtest(px, list(syms), sma_window=sma,
                                 vol_window=VOL, leverage=LEV, cost_bps=COST)

def fmt(r):
    if r is None:
        return "  N/A"
    return (f"CAGR {r['cagr']:5.1f}%  DD {r['max_dd']:6.1f}%  "
            f"Sharpe {r['sharpe']:.2f}  Calmar {r['calmar']:.2f}  "
            f"PF {r['profit_factor']:.1f}  WorstYr {r['worst_year']:.1f}%")


COMBOS = {
    "A: QQQ/TLT/GLD/VNQ": ["QQQ","TLT","GLD","VNQ"],
    "B: SPY/TLT/GLD/VNQ": ["SPY","TLT","GLD","VNQ"],
    "C: QQQ/TLT/GLD":     ["QQQ","TLT","GLD"],
    "D: SPY/TLT/GLD":     ["SPY","TLT","GLD"],
    "E: QQQ/TLT/VNQ":     ["QQQ","TLT","VNQ"],
    "F: SPY/TLT/VNQ":     ["SPY","TLT","VNQ"],
}

# ═══════════════════════════════════════════════════════════
# TEST 1 — SPY vs QQQ
# ═══════════════════════════════════════════════════════════
print("\n" + "="*80)
print("TEST 1 — SPY vs QQQ (tech bias)")
print("="*80)
for name, syms in [("A: QQQ/TLT/GLD/VNQ", ["QQQ","TLT","GLD","VNQ"]),
                    ("B: SPY/TLT/GLD/VNQ", ["SPY","TLT","GLD","VNQ"]),
                    ("C: QQQ/TLT/GLD",     ["QQQ","TLT","GLD"]),
                    ("D: SPY/TLT/GLD",     ["SPY","TLT","GLD"])]:
    r = bt(syms)
    print(f"  {name:<25s} {fmt(r)}")

# ═══════════════════════════════════════════════════════════
# TEST 2 — With/without GLD (gold bias)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*80)
print("TEST 2 — With/without GLD (gold bias)")
print("="*80)
for name, syms in [("A: QQQ/TLT/GLD/VNQ", ["QQQ","TLT","GLD","VNQ"]),
                    ("E: QQQ/TLT/VNQ",     ["QQQ","TLT","VNQ"]),
                    ("B: SPY/TLT/GLD/VNQ", ["SPY","TLT","GLD","VNQ"]),
                    ("F: SPY/TLT/VNQ",     ["SPY","TLT","VNQ"])]:
    r = bt(syms)
    print(f"  {name:<25s} {fmt(r)}")

# ═══════════════════════════════════════════════════════════
# TEST 3 — Sub-periods (recency bias)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*80)
print("TEST 3 — Sub-periods (recency bias)")
print("="*80)
PERIODS = [
    ("P1 2006-2012", "2006-01-01", "2012-12-31"),
    ("P2 2013-2019", "2013-01-01", "2019-12-31"),
    ("P3 2020-2026", "2020-01-01", "2026-12-31"),
]
for pname, s, e in PERIODS:
    print(f"\n  ── {pname} ──")
    for name, syms in [("A: QQQ/TLT/GLD/VNQ", ["QQQ","TLT","GLD","VNQ"]),
                        ("B: SPY/TLT/GLD/VNQ", ["SPY","TLT","GLD","VNQ"]),
                        ("C: QQQ/TLT/GLD",     ["QQQ","TLT","GLD"]),
                        ("D: SPY/TLT/GLD",     ["SPY","TLT","GLD"])]:
        r = bt(syms, start=s, end=e)
        if r:
            print(f"    {name:<25s} CAGR {r['cagr']:5.1f}%  "
                  f"DD {r['max_dd']:6.1f}%  Sharpe {r['sharpe']:.2f}")
        else:
            print(f"    {name:<25s} N/A (insufficient data)")

# ═══════════════════════════════════════════════════════════
# TEST 4 — SMA sensitivity (curve fitting)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*80)
print("TEST 4 — SMA sensitivity (curve fitting check)")
print("="*80)
print(f"\n  {'SMA':>5s} | {'A: QQQ/TLT/GLD/VNQ':^40s} | {'B: SPY/TLT/GLD/VNQ':^40s}")
print(f"  {'':>5s} | {'CAGR':>6s} {'DD':>7s} {'Sharpe':>7s} {'Calmar':>7s} | "
      f"{'CAGR':>6s} {'DD':>7s} {'Sharpe':>7s} {'Calmar':>7s}")
print("  " + "-"*95)
for sma in [80, 100, 120, 150, 175, 200, 250]:
    rA = bt(["QQQ","TLT","GLD","VNQ"], sma=sma)
    rB = bt(["SPY","TLT","GLD","VNQ"], sma=sma)
    def s(r):
        if r is None: return "N/A"
        return f"{r['cagr']:5.1f}% {r['max_dd']:6.1f}% {r['sharpe']:6.2f} {r['calmar']:6.2f}"
    print(f"  {sma:>5d} | {s(rA):>40s} | {s(rB):>40s}")

# ═══════════════════════════════════════════════════════════
# TEST 5 — Rolling correlation (structural stability)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*80)
print("TEST 5 — Rolling 252d correlation")
print("="*80)

px = prices[["QQQ","TLT","GLD","VNQ"]].dropna()
rets = px.pct_change().dropna()
window = 252

pairs = [("QQQ","TLT"), ("QQQ","GLD"), ("QQQ","VNQ"), ("TLT","GLD")]
fig, axes = plt.subplots(len(pairs), 1, figsize=(14, 10), sharex=True)
for i, (a, b) in enumerate(pairs):
    rc = rets[a].rolling(window).corr(rets[b])
    axes[i].plot(rc.index, rc.values, lw=1.2, color='steelblue')
    axes[i].axhline(0, color='black', lw=0.5)
    axes[i].axhline(rc.mean(), color='red', lw=0.8, ls='--',
                     label=f'mean={rc.mean():.2f}')
    # Mark crisis periods
    for crisis, c in [("2008", "orange"), ("2020", "red"), ("2022", "purple")]:
        yr = int(crisis)
        axes[i].axvspan(f"{yr}-01-01", f"{yr}-12-31", alpha=0.15, color=c)
    axes[i].set_ylabel(f"{a}/{b}")
    axes[i].set_ylim(-1, 1)
    axes[i].legend(loc='lower right', fontsize=9)
    axes[i].grid(alpha=0.3)
    # Report stats
    print(f"  {a}/{b}: mean={rc.mean():.3f}  std={rc.std():.3f}  "
          f"min={rc.min():.3f}  max={rc.max():.3f}  "
          f"2008={rc.loc['2008'].mean():.3f}  "
          f"2020={rc.loc['2020'].mean():.3f}  "
          f"2022={rc.loc['2022'].mean():.3f}")

axes[0].set_title("Rolling 252-day Correlation — QQQ/TLT/GLD/VNQ\n"
                   "(orange=2008, red=2020, purple=2022)")
axes[-1].xaxis.set_major_locator(mdates.YearLocator(2))
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.tight_layout()
fig.savefig("rolling_correlations.png", dpi=140)
print("  → Saved rolling_correlations.png")

# ═══════════════════════════════════════════════════════════
# TEST 6 — 2022 month-by-month zoom
# ═══════════════════════════════════════════════════════════
print("\n" + "="*80)
print("TEST 6 — 2022 month-by-month zoom")
print("="*80)

syms = ["QQQ","TLT","GLD","VNQ"]
px22 = prices[syms].loc["2021-06-01":"2023-01-31"].dropna()
sma150 = px22.rolling(150).mean()
vol40 = px22.pct_change().rolling(40).std() * np.sqrt(252)

# Monthly snapshots
monthly = px22.resample("ME").last()
sma_m = sma150.resample("ME").last()

print(f"\n  {'Month':>8s} | ", end="")
for s in syms:
    print(f"{'ON/OFF':>6s} {'Vol%':>5s} {'Wgt%':>5s} | ", end="")
print(f"{'Cash%':>5s} {'MonthRet':>8s}")
print("  " + "-"*90)

# Run the backtest to get actual monthly returns
r22 = trend_parity_backtest(prices, syms)
if r22 and 'equity_series' in r22:
    eq = r22['equity_series']
    eq_22 = eq.loc["2021-12-31":"2023-01-31"]
    monthly_ret = eq_22.resample("ME").last().pct_change().dropna()

for d in monthly.loc["2022-01":"2022-12"].index:
    inv_vols = {}
    for s in syms:
        on = monthly.loc[d, s] > sma_m.loc[d, s] if d in sma_m.index else False
        v = vol40.loc[:d].iloc[-1][s] if d <= vol40.index[-1] else np.nan
        if on and v > 0:
            inv_vols[s] = 1.0 / v
        else:
            inv_vols[s] = 0.0
    total = sum(inv_vols.values())

    print(f"  {d.strftime('%Y-%m'):>8s} | ", end="")
    for s in syms:
        on = monthly.loc[d, s] > sma_m.loc[d, s] if d in sma_m.index else False
        v = vol40.loc[:d].iloc[-1][s] * 100 if d <= vol40.index[-1] else 0
        w = (inv_vols[s] / total * 100) if total > 0 else 0
        status = "ON " if on else "OFF"
        print(f"{status:>6s} {v:4.0f}% {w:4.0f}% | ", end="")
    cash = 100 - (sum(inv_vols.values()) / total * 100 if total > 0 else 0)
    mr = monthly_ret.loc[d] * 100 if d in monthly_ret.index else 0
    print(f"{cash:4.0f}% {mr:>+7.2f}%")

# Also show each asset's monthly return in 2022
print(f"\n  Asset monthly returns in 2022:")
for s in syms:
    px_s = prices[s].loc["2021-12-31":"2022-12-31"]
    yr_ret = px_s.iloc[-1] / px_s.iloc[0] - 1
    print(f"    {s}: {yr_ret*100:+.1f}% for 2022")

print("\n" + "="*80)
print("  ALL STRESS TESTS COMPLETE")
print("="*80)
