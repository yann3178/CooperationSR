"""
cb_twap_tests.py — Circuit Breaker + TWAP analysis (Phases 1-5)
Requires: cb_twap_engine.py + data_ohlcv/*.csv
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

from cb_twap_engine import (load_all_ohlcv, run_backtest, compute_metrics,
                             pretty_metrics, summarize_cb_events, SYMBOLS)

print("Loading OHLCV data...")
ohlcv = load_all_ohlcv()
for s in SYMBOLS:
    df = ohlcv[s]
    print(f"  {s}: {df.index[0].date()} -> {df.index[-1].date()} ({len(df)})")

def bt(leverage=1.2, exec_mode='open', cb_threshold=None, cb_cooldown=5,
       cb_reentry='next_rebal', cb_peak_mode='monthly', impact_bps=0,
       start_date=None):
    return run_backtest(
        ohlcv_data=ohlcv, leverage=leverage, exec_mode=exec_mode,
        cb_enabled=(cb_threshold is not None),
        cb_threshold=cb_threshold or -0.10,
        cb_cooldown_days=cb_cooldown,
        cb_reentry_mode=cb_reentry,
        cb_peak_mode=cb_peak_mode,
        impact_bps=impact_bps,
        start_date=start_date,
    )

def m2d(m):
    return {'cagr': round(m.cagr*100,2), 'vol': round(m.vol*100,2),
            'sharpe': round(m.sharpe,2), 'max_dd_close': round(m.max_dd_close*100,2),
            'max_dd_intraday': round(m.max_dd_intraday*100,2),
            'calmar': round(m.calmar,2), 'pf': round(m.profit_factor,2),
            'final': round(m.final_equity,0)}

# PHASE 1
print("\n" + "="*90)
print("PHASE 1 — Baseline (lev 1.2, open exec, no CB)")
print("="*90)
bl = bt(cb_threshold=None)
bm = compute_metrics(bl)
print(pretty_metrics(bm, "Baseline"))

# PHASE 2A
print("\n" + "="*90)
print("PHASE 2A — CB threshold sensitivity")
print("="*90)
print(f"  {'Seuil':>7s} {'CAGR':>7s} {'DD_c2c':>8s} {'DD_intra':>9s} {'Sharpe':>7s} {'Calmar':>7s} {'#Trig':>6s} {'%Cash':>6s}")
print("  " + "-"*60)
best_thresh = None; best_calmar = 0
for thresh in [None, -0.05, -0.08, -0.10, -0.12, -0.15]:
    res = bt(cb_threshold=thresh)
    m = m2d(compute_metrics(res))
    n_trig = len(res.cb_events)
    pct_cash = res.in_cash_mode.mean()*100
    label = "None" if thresh is None else f"{thresh*100:.0f}%"
    print(f"  {label:>7s} {m['cagr']:>6.2f}% {m['max_dd_close']:>7.2f}% "
          f"{m['max_dd_intraday']:>8.2f}% {m['sharpe']:>7.2f} "
          f"{m['calmar']:>7.2f} {n_trig:>6d} {pct_cash:>5.1f}%")
    if thresh is not None and m['calmar'] > best_calmar:
        best_calmar = m['calmar']; best_thresh = thresh
if best_thresh is None: best_thresh = -0.10
print(f"\n  Best threshold by Calmar: {best_thresh*100:.0f}%")

# PHASE 2B
print(f"\n── PHASE 2B — Cooldown (threshold={best_thresh*100:.0f}%) ──")
print(f"  {'Cooldown':>10s} {'CAGR':>7s} {'DD_c2c':>8s} {'Calmar':>7s} {'#Trig':>6s}")
for cd in [0, 3, 5, 10, 20]:
    res = bt(cb_threshold=best_thresh, cb_cooldown=cd, cb_reentry='immediate')
    m = m2d(compute_metrics(res))
    print(f"  {cd:>10d} {m['cagr']:>6.2f}% {m['max_dd_close']:>7.2f}% {m['calmar']:>7.2f} {len(res.cb_events):>6d}")
res = bt(cb_threshold=best_thresh, cb_reentry='next_rebal')
m = m2d(compute_metrics(res))
print(f"  {'next_rebal':>10s} {m['cagr']:>6.2f}% {m['max_dd_close']:>7.2f}% {m['calmar']:>7.2f} {len(res.cb_events):>6d}")

# PHASE 2C
print(f"\n── PHASE 2C — Reentry mode ──")
for mode in ['next_rebal', 'immediate', 'sma_confirm']:
    res = bt(cb_threshold=best_thresh, cb_cooldown=5, cb_reentry=mode)
    m = m2d(compute_metrics(res))
    print(f"  {mode:<15s} CAGR {m['cagr']:>6.2f}%  DD {m['max_dd_close']:>7.2f}%  Calmar {m['calmar']:.2f}")

# PHASE 2D
print(f"\n── PHASE 2D — Trigger classification ──")
res_best = bt(cb_threshold=best_thresh, cb_cooldown=5, cb_reentry='next_rebal')
events = res_best.cb_events
print(f"  Total triggers: {len(events)}")
good = neut = bad = 0
for i, ev in enumerate(events):
    r21 = ev.qqq_fwd_21d or ev.fwd_21d_ret
    if r21 is None: verdict = "?"
    elif r21 < -0.05: verdict = "GOOD"; good += 1
    elif r21 > 0.05: verdict = "BAD"; bad += 1
    else: verdict = "neutral"; neut += 1
    r21_s = f"{r21*100:+.1f}%" if r21 is not None else "N/A"
    td = ev.date.strftime('%Y-%m-%d') if hasattr(ev.date, 'strftime') else str(ev.date)
    print(f"    {i+1}. {td}  DD={ev.drawdown_pct*100:.1f}%  +21d={r21_s}  -> {verdict}")
print(f"  Good: {good}  Neutral: {neut}  Bad: {bad}")

# PHASE 2E
print(f"\n── PHASE 2E — Threshold x Leverage ──")
print(f"  {'Lev':>4s} {'Thresh':>7s} {'CAGR':>7s} {'DD_c2c':>8s} {'Calmar':>7s} {'#Trig':>6s}")
for lev in [1.0, 1.2, 1.5]:
    for thresh in [None, -0.08, -0.10, -0.12]:
        res = bt(leverage=lev, cb_threshold=thresh)
        m = m2d(compute_metrics(res)); n = len(res.cb_events)
        tl = "None" if thresh is None else f"{thresh*100:.0f}%"
        print(f"  {lev:>4.1f} {tl:>7s} {m['cagr']:>6.2f}% {m['max_dd_close']:>7.2f}% {m['calmar']:>7.2f} {n:>6d}")

# PHASE 3F
print("\n" + "="*90)
print("PHASE 3F — Execution mode comparison")
print("="*90)
for mode in ['open', 'ohlc_avg', 'twap_2d', 'twap_3d', 'close']:
    res = bt(exec_mode=mode, cb_threshold=None)
    m = m2d(compute_metrics(res))
    print(f"  {mode:<15s} CAGR {m['cagr']:>6.2f}%  DD {m['max_dd_close']:>7.2f}%  Sharpe {m['sharpe']:.2f}  ${m['final']:>12,.0f}")

# PHASE 3G
print(f"\n── PHASE 3G — Impact by portfolio size ──")
for size, impact in [(100000,1),(1000000,5),(5000000,12),(10000000,20)]:
    ro = bt(exec_mode='open', impact_bps=impact, cb_threshold=None)
    rt = bt(exec_mode='twap_3d', impact_bps=int(impact/np.sqrt(3)), cb_threshold=None)
    mo, mt = m2d(compute_metrics(ro)), m2d(compute_metrics(rt))
    print(f"  ${size:>10,.0f}  {impact:>2d}bps  open={mo['cagr']:>6.2f}%  twap3={mt['cagr']:>6.2f}%  {mt['cagr']-mo['cagr']:>+5.2f}")

# PHASE 4
print("\n" + "="*90)
print("PHASE 4 — Combined")
print("="*90)
for label, thresh, em in [("Baseline",None,'open'),(f"CB {best_thresh*100:.0f}%",best_thresh,'open'),
                           ("TWAP 3d",None,'twap_3d'),(f"CB+TWAP",best_thresh,'twap_3d')]:
    res = bt(cb_threshold=thresh, exec_mode=em)
    m = m2d(compute_metrics(res)); n = len(res.cb_events)
    print(f"  {label:<20s} CAGR {m['cagr']:>6.2f}%  DDc {m['max_dd_close']:>7.2f}%  DDi {m['max_dd_intraday']:>7.2f}%  Sh {m['sharpe']:.2f}  Cal {m['calmar']:.2f}  #{n}")

# PHASE 5I
print("\n── PHASE 5I — Monte Carlo 500 sims ──")
np.random.seed(42)
for label, thresh in [("Baseline",None),(f"CB {best_thresh*100:.0f}%",best_thresh)]:
    res = bt(cb_threshold=thresh)
    eq = pd.Series(res.equity, index=res.dates)
    mo = eq.resample('ME').last().pct_change().dropna().values
    nm = len(mo); cagrs, dds = [], []
    for _ in range(500):
        idx = np.random.randint(0, nm, size=nm); sim = mo[idx]
        eqs = np.cumprod(1+sim); yrs = nm/12
        cagrs.append((eqs[-1]**(1/yrs)-1)*100)
        pk = np.maximum.accumulate(eqs); dds.append(((eqs-pk)/pk).min()*100)
    sc, sd = np.array(cagrs), np.array(dds)
    print(f"\n  {label}: CAGR P10={np.percentile(sc,10):.1f}% med={np.median(sc):.1f}% P90={np.percentile(sc,90):.1f}%")
    print(f"         DD   P10={np.percentile(sd,10):.1f}% med={np.median(sd):.1f}%  Prob>-25%: {(sd<-25).mean()*100:.1f}%")

# Chart
print("\nGenerating chart...")
bl_res = bt(cb_threshold=None); cb_res = bt(cb_threshold=best_thresh)
bl_eq = pd.Series(bl_res.equity, index=bl_res.dates)
cb_eq = pd.Series(cb_res.equity, index=cb_res.dates)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 2]})
ax1.plot(bl_eq.index, bl_eq.values, label='Baseline', color='steelblue', lw=1.5)
ax1.plot(cb_eq.index, cb_eq.values, label=f'CB {best_thresh*100:.0f}%', color='darkorange', lw=1.5)
for ev in cb_res.cb_events: ax1.axvline(ev.date, color='red', alpha=0.3, lw=0.8)
ax1.set_ylabel('Equity'); ax1.set_yscale('log')
ax1.set_title(f'Baseline vs CB {best_thresh*100:.0f}%'); ax1.legend(); ax1.grid(alpha=0.3, which='both')
dd_bl = (bl_eq/bl_eq.cummax()-1)*100; dd_cb = (cb_eq/cb_eq.cummax()-1)*100
ax2.fill_between(bl_eq.index, dd_bl, 0, color='steelblue', alpha=0.5, label='Baseline')
ax2.fill_between(cb_eq.index, dd_cb, 0, color='darkorange', alpha=0.5, label='CB')
ax2.set_ylabel('DD %'); ax2.grid(alpha=0.3); ax2.legend(loc='lower left')
fig.tight_layout(); fig.savefig('cb_twap_chart.png', dpi=140)
print("  -> Saved cb_twap_chart.png")
print("\n" + "="*90 + "\n  COMPLETE\n" + "="*90)
