"""
leverage_analysis.py — Trend-Parity Optimal Leverage & CAGR Targets
====================================================================

Phases:
  1. Leverage curve 1.0-3.0 (no margin cost)
  2. Same with realistic IBKR margin cost (5.5%)
  3. Three risk profiles (Conservative / Moderate / Aggressive)
  4. vs SPY buy-and-hold leveraged
  5. Monte Carlo bootstrap (1000 sims)
  6. SPY combo variant
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

from backtest_universe import download_data, trend_parity_backtest, CANDIDATES

# ─── Config ──────────────────────────────────────────
COMBOS = {
    'QQQ_combo': ['QQQ', 'TLT', 'GLD', 'VNQ'],
    'SPY_combo': ['SPY', 'TLT', 'GLD', 'VNQ'],
}
SMA = 150
VOL = 40
COST = 5
CAPITAL = 100000
LEVERAGES = [round(1.0 + i * 0.1, 1) for i in range(21)]  # 1.0-3.0
MARGIN_COST = 0.055  # 5.5% annual

print("Loading data...")
prices = download_data(list({**CANDIDATES, 'SPY': 'S&P 500'}.keys()))


def bt_with_margin(syms, leverage, margin_cost=0.0):
    """Run backtest and subtract daily margin cost from returns."""
    r = trend_parity_backtest(prices, syms, sma_window=SMA, vol_window=VOL,
                               leverage=leverage, cost_bps=COST)
    if r is None:
        return None
    if margin_cost > 0 and leverage > 1.0:
        # Re-run to get equity series, then deduct margin
        eq = r['equity_series']
        borrowed_frac = leverage - 1.0
        daily_cost = borrowed_frac * margin_cost / 252
        # Deduct cost from daily returns
        rets = eq.pct_change().fillna(0) - daily_cost
        eq_net = (1 + rets).cumprod() * CAPITAL
        years = (eq_net.index[-1] - eq_net.index[0]).days / 365.25
        cagr = (eq_net.iloc[-1] / CAPITAL) ** (1 / years) - 1
        peak = eq_net.cummax()
        dd = (eq_net - peak) / peak
        max_dd = dd.min()
        vol_ann = rets.std() * np.sqrt(252)
        sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
        calmar = cagr / abs(max_dd) if max_dd < 0 else 0
        # Worst year
        ann_ret = rets.resample('YE').sum()
        worst_yr = ann_ret.min()
        worst_yr_date = ann_ret.idxmin().year if len(ann_ret) > 0 else 0
        # Duration underwater
        underwater = dd < -0.01
        uw_runs = underwater.astype(int).groupby((~underwater).cumsum()).cumsum()
        max_uw_days = uw_runs.max()
        return {
            'leverage': leverage,
            'cagr': round(cagr * 100, 2),
            'max_dd': round(max_dd * 100, 2),
            'sharpe': round(sharpe, 2),
            'calmar': round(calmar, 2),
            'vol': round(vol_ann * 100, 2),
            'worst_year': round(worst_yr * 100, 2),
            'worst_year_date': worst_yr_date,
            'max_uw_days': int(max_uw_days),
            'final_equity': round(eq_net.iloc[-1], 0),
            'equity_series': eq_net,
        }
    else:
        # Add extra fields from the raw result
        eq = r['equity_series']
        rets = eq.pct_change().fillna(0)
        ann_ret = rets.resample('YE').sum()
        dd = (eq - eq.cummax()) / eq.cummax()
        underwater = dd < -0.01
        uw_runs = underwater.astype(int).groupby((~underwater).cumsum()).cumsum()
        r['leverage'] = leverage
        r['vol'] = round(rets.std() * np.sqrt(252) * 100, 2)
        r['max_uw_days'] = int(uw_runs.max())
        return r


# ═══════════════════════════════════════════════════════
# PHASE 1 — Leverage curve (no margin cost)
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 1 — Leverage curve (QQQ/TLT/GLD/VNQ, no margin cost)")
print("="*80)
print(f"  {'Lev':>4s} {'CAGR':>7s} {'MaxDD':>7s} {'Sharpe':>7s} {'Calmar':>7s} "
      f"{'Vol':>7s} {'WorstYr':>8s} {'UW_days':>8s}")
print("  " + "-"*65)

results_p1 = []
for lev in LEVERAGES:
    r = bt_with_margin(COMBOS['QQQ_combo'], lev, margin_cost=0)
    if r:
        results_p1.append(r)
        print(f"  {lev:4.1f} {r['cagr']:6.1f}% {r['max_dd']:6.1f}% "
              f"{r['sharpe']:6.2f} {r['calmar']:6.2f} {r['vol']:6.1f}% "
              f"{r['worst_year']:7.1f}% {r['max_uw_days']:7d}d")

# Kelly point
df1 = pd.DataFrame(results_p1)
kelly_idx = df1['cagr'].idxmax()
kelly_lev = df1.loc[kelly_idx, 'leverage']
kelly_cagr = df1.loc[kelly_idx, 'cagr']
print(f"\n  Kelly point: leverage={kelly_lev:.1f}, CAGR={kelly_cagr:.1f}%")

# ═══════════════════════════════════════════════════════
# PHASE 2 — With IBKR margin cost
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print(f"PHASE 2 — With margin cost ({MARGIN_COST*100:.1f}% annual)")
print("="*80)
print(f"  {'Lev':>4s} {'CAGR_gross':>10s} {'CAGR_net':>9s} {'DD_net':>7s} "
      f"{'Sharpe':>7s} {'Calmar':>7s} {'WorstYr':>8s}")
print("  " + "-"*65)

results_p2 = []
for lev in LEVERAGES:
    r_gross = bt_with_margin(COMBOS['QQQ_combo'], lev, margin_cost=0)
    r_net = bt_with_margin(COMBOS['QQQ_combo'], lev, margin_cost=MARGIN_COST)
    if r_gross and r_net:
        results_p2.append({**r_net, 'cagr_gross': r_gross['cagr']})
        print(f"  {lev:4.1f} {r_gross['cagr']:9.1f}% {r_net['cagr']:8.1f}% "
              f"{r_net['max_dd']:6.1f}% {r_net['sharpe']:6.2f} "
              f"{r_net['calmar']:6.2f} {r_net['worst_year']:7.1f}%")

df2 = pd.DataFrame(results_p2)
kelly_net_idx = df2['cagr'].idxmax()
kelly_net_lev = df2.loc[kelly_net_idx, 'leverage']
kelly_net_cagr = df2.loc[kelly_net_idx, 'cagr']
print(f"\n  Kelly (net): leverage={kelly_net_lev:.1f}, CAGR={kelly_net_cagr:.1f}%")

# ═══════════════════════════════════════════════════════
# CHART — Leverage curves
# ═══════════════════════════════════════════════════════
fig, ax1 = plt.subplots(figsize=(12, 7))
ax2 = ax1.twinx()

levs = df2['leverage']
ax1.plot(levs, df2['cagr_gross'], 'b-', lw=2, label='CAGR gross')
ax1.plot(levs, df2['cagr'], 'b--', lw=2, label='CAGR net (after margin)')
ax2.plot(levs, df2['max_dd'], 'r-', lw=2, label='MaxDD (net)')
ax2.plot(levs, df2['worst_year'], 'r:', lw=1.5, label='Worst year (net)')

for target, color in [(12, 'green'), (16, 'orange'), (20, 'purple')]:
    ax1.axhline(target, color=color, ls='--', lw=0.8, alpha=0.7)
    ax1.text(3.05, target, f'{target}%', color=color, fontsize=9, va='center')

ax1.axvline(kelly_net_lev, color='gray', ls=':', lw=1, alpha=0.5)
ax1.text(kelly_net_lev+0.05, kelly_net_cagr-1, f'Kelly={kelly_net_lev:.1f}',
         fontsize=9, color='gray')

ax1.set_xlabel('Leverage')
ax1.set_ylabel('CAGR (%)', color='blue')
ax2.set_ylabel('Drawdown (%)', color='red')
ax1.set_title('Trend-Parity Leverage Curve — QQQ/TLT/GLD/VNQ\n'
              f'(margin cost {MARGIN_COST*100:.1f}%, SMA={SMA})')
ax1.legend(loc='upper left')
ax2.legend(loc='lower left')
ax1.grid(alpha=0.3)
ax1.set_xlim(1.0, 3.0)
fig.tight_layout()
fig.savefig('leverage_curve.png', dpi=140)
print("\n  → Saved leverage_curve.png")

# ═══════════════════════════════════════════════════════
# PHASE 3 — Risk profiles
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 3 — Risk profiles (QQQ combo, net of margin)")
print("="*80)

PROFILES = {
    'Conservative (CAGR≥12%)': lambda r: r['cagr'] >= 12,
    'Moderate (CAGR≥16%)':     lambda r: r['cagr'] >= 16,
    'Aggressive (CAGR≥20%)':   lambda r: r['cagr'] >= 20,
}

for profile, cond in PROFILES.items():
    candidates = [r for r in results_p2 if cond(r)]
    if not candidates:
        # Find closest
        best = max(results_p2, key=lambda r: r['cagr'])
        print(f"\n  {profile}: NOT ACHIEVABLE (max net CAGR = {best['cagr']:.1f}%)")
        continue
    # Pick lowest leverage that meets the target
    best = min(candidates, key=lambda r: r['leverage'])
    print(f"\n  {profile}")
    print(f"    Leverage optimal     : {best['leverage']:.1f}")
    print(f"    CAGR gross           : {best['cagr_gross']:.1f}%")
    print(f"    CAGR net             : {best['cagr']:.1f}%")
    print(f"    MaxDD                : {best['max_dd']:.1f}%")
    print(f"    Vol annualisée       : {best['vol']:.1f}%")
    print(f"    Sharpe               : {best['sharpe']:.2f}")
    print(f"    Calmar               : {best['calmar']:.2f}")
    print(f"    Worst year           : {best['worst_year']:.1f}% ({best['worst_year_date']})")
    print(f"    Max underwater       : {best['max_uw_days']} days")
    capital_req = CAPITAL / best['leverage']
    print(f"    Capital IBKR for $100k: ${capital_req:,.0f}")

# ═══════════════════════════════════════════════════════
# PHASE 4 — vs SPY buy-and-hold leveraged
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 4 — Trend-Parity vs SPY buy-and-hold (leveraged)")
print("="*80)

print(f"\n  {'Strategy':<30s} {'Lev':>4s} {'CAGR':>7s} {'MaxDD':>7s} "
      f"{'Sharpe':>7s} {'Calmar':>7s}")
print("  " + "-"*70)

# SPY buy and hold with margin cost
for lev in [1.0, 1.5, 2.0, 2.5]:
    # SPY B&H = all-in SPY, no timing
    spy = prices['SPY'].dropna()
    rets = spy.pct_change().fillna(0) * lev
    if lev > 1:
        rets -= (lev - 1) * MARGIN_COST / 252
    eq = (1 + rets).cumprod() * CAPITAL
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / CAPITAL) ** (1 / years) - 1
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    vol = rets.std() * np.sqrt(252)
    sharpe = rets.mean() / rets.std() * np.sqrt(252)
    calmar = cagr / abs(dd) if dd < 0 else 0
    print(f"  {'SPY B&H':<30s} {lev:4.1f} {cagr*100:6.1f}% {dd*100:6.1f}% "
          f"{sharpe:6.2f} {calmar:6.2f}")

# Trend-Parity QQQ combo
for lev in [1.0, 1.5, 2.0, 2.5]:
    r = bt_with_margin(COMBOS['QQQ_combo'], lev, MARGIN_COST)
    if r:
        print(f"  {'TP QQQ/TLT/GLD/VNQ':<30s} {lev:4.1f} {r['cagr']:6.1f}% "
              f"{r['max_dd']:6.1f}% {r['sharpe']:6.2f} {r['calmar']:6.2f}")

# Trend-Parity SPY combo
for lev in [1.0, 1.5, 2.0, 2.5]:
    r = bt_with_margin(COMBOS['SPY_combo'], lev, MARGIN_COST)
    if r:
        print(f"  {'TP SPY/TLT/GLD/VNQ':<30s} {lev:4.1f} {r['cagr']:6.1f}% "
              f"{r['max_dd']:6.1f}% {r['sharpe']:6.2f} {r['calmar']:6.2f}")

# ═══════════════════════════════════════════════════════
# PHASE 5 — Monte Carlo bootstrap
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 5 — Monte Carlo (1000 sims, monthly block bootstrap)")
print("="*80)

N_SIM = 1000
np.random.seed(42)

for lev in [1.0, 1.5, 2.0]:
    r = bt_with_margin(COMBOS['QQQ_combo'], lev, MARGIN_COST)
    if r is None:
        continue
    eq = r['equity_series']
    monthly = eq.resample('ME').last().pct_change().dropna().values
    n_months = len(monthly)

    sim_cagr = []
    sim_dd = []
    sim_worst_yr = []
    for _ in range(N_SIM):
        # Block bootstrap: resample monthly returns with replacement
        idx = np.random.randint(0, n_months, size=n_months)
        sim_ret = monthly[idx]
        sim_eq = np.cumprod(1 + sim_ret)
        sim_eq = np.insert(sim_eq, 0, 1.0)
        # CAGR
        years = n_months / 12
        c = sim_eq[-1] ** (1 / years) - 1
        sim_cagr.append(c * 100)
        # MaxDD
        peak = np.maximum.accumulate(sim_eq)
        dd = (sim_eq - peak) / peak
        sim_dd.append(dd.min() * 100)
        # Worst "year" (worst rolling 12-month)
        if len(sim_ret) >= 12:
            yr_rets = [np.prod(1 + sim_ret[i:i+12]) - 1
                       for i in range(0, len(sim_ret)-11)]
            sim_worst_yr.append(min(yr_rets) * 100)
        else:
            sim_worst_yr.append(0)

    sc = np.array(sim_cagr)
    sd = np.array(sim_dd)
    sw = np.array(sim_worst_yr)

    print(f"\n  Leverage {lev:.1f} (net of {MARGIN_COST*100:.1f}% margin)")
    print(f"    CAGR distribution:")
    print(f"      P10={np.percentile(sc,10):.1f}%  P25={np.percentile(sc,25):.1f}%  "
          f"Median={np.median(sc):.1f}%  P75={np.percentile(sc,75):.1f}%  "
          f"P90={np.percentile(sc,90):.1f}%")
    print(f"    MaxDD distribution:")
    print(f"      P10={np.percentile(sd,10):.1f}%  Median={np.median(sd):.1f}%  "
          f"P90={np.percentile(sd,90):.1f}%")
    print(f"    Worst 12-month return:")
    print(f"      P10={np.percentile(sw,10):.1f}%  Median={np.median(sw):.1f}%")
    print(f"    Prob(CAGR < 0% over full period) = {(sc < 0).mean()*100:.1f}%")
    print(f"    Prob(CAGR < 5% over full period) = {(sc < 5).mean()*100:.1f}%")
    print(f"    Prob(MaxDD > -30%) = {(sd < -30).mean()*100:.1f}%")
    print(f"    Prob(MaxDD > -40%) = {(sd < -40).mean()*100:.1f}%")
    print(f"    Prob(MaxDD > -50%) = {(sd < -50).mean()*100:.1f}%")

# ═══════════════════════════════════════════════════════
# PHASE 6 — SPY combo profiles
# ═══════════════════════════════════════════════════════
print("\n" + "="*80)
print("PHASE 6 — SPY combo leverage curve (net of margin)")
print("="*80)
print(f"  {'Lev':>4s} {'CAGR_net':>9s} {'MaxDD':>7s} {'Sharpe':>7s} "
      f"{'Calmar':>7s} {'WorstYr':>8s}")
print("  " + "-"*50)

results_spy = []
for lev in LEVERAGES:
    r = bt_with_margin(COMBOS['SPY_combo'], lev, MARGIN_COST)
    if r:
        results_spy.append(r)
        print(f"  {lev:4.1f} {r['cagr']:8.1f}% {r['max_dd']:6.1f}% "
              f"{r['sharpe']:6.2f} {r['calmar']:6.2f} {r['worst_year']:7.1f}%")

df_spy = pd.DataFrame(results_spy)
kelly_spy = df_spy.loc[df_spy['cagr'].idxmax()]
print(f"\n  Kelly (SPY, net): leverage={kelly_spy['leverage']:.1f}, "
      f"CAGR={kelly_spy['cagr']:.1f}%")

for profile, target in [('Conservative 12%', 12), ('Moderate 16%', 16),
                         ('Aggressive 20%', 20)]:
    cands = [r for r in results_spy if r['cagr'] >= target]
    if cands:
        best = min(cands, key=lambda r: r['leverage'])
        print(f"  {profile}: lev={best['leverage']:.1f} → "
              f"CAGR {best['cagr']:.1f}% / DD {best['max_dd']:.1f}%")
    else:
        best = max(results_spy, key=lambda r: r['cagr'])
        print(f"  {profile}: NOT ACHIEVABLE (max={best['cagr']:.1f}% "
              f"at lev={best['leverage']:.1f})")

print("\n" + "="*80)
print("  ALL PHASES COMPLETE")
print("="*80)
