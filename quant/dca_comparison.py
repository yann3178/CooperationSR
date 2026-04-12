"""
dca_comparison.py — Lump Sum vs DCA vs DCA+ZAR
================================================

Same universe as Trend-Parity (QQQ/TLT/GLD/VNQ), same SMA/vol rules,
but three different capital deployment strategies.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

from backtest_universe import download_data, CANDIDATES

SYMBOLS = ['QQQ', 'TLT', 'GLD', 'VNQ']
SMA_WINDOW = 150
VOL_WINDOW = 40
COST_BPS = 5         # 5 bps per side on any transaction
BIL_YIELD = 0.02     # 2% annual yield on cash reserve (conservative)

print("Loading data...")
prices_full = download_data(SYMBOLS)
prices = prices_full[SYMBOLS].dropna()
print(f"Available: {prices.index[0].date()} -> {prices.index[-1].date()} "
      f"({len(prices)} bars)")


# ═══════════════════════════════════════════════════════
# Indicators (vectorised, computed once)
# ═══════════════════════════════════════════════════════
sma150 = prices.rolling(SMA_WINDOW).mean()
vol40 = prices.pct_change().rolling(VOL_WINDOW).std() * np.sqrt(252)

# ZAR conditions (vectorised)
def compute_zar_signals(prices, rsi_thresh=40, near_low_pct=0.03,
                        bb_mult=1.02):
    """Return a DataFrame (date, symbol) of booleans indicating ZAR."""
    sigs = pd.DataFrame(False, index=prices.index, columns=prices.columns)
    for sym in prices.columns:
        close = prices[sym]
        # RSI 14
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs)
        rsi = rsi.fillna(50)
        # Near 20d low
        low20 = close.rolling(20).min()
        near_low = (close - low20) / low20 < near_low_pct
        # Near Bollinger lower
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_lower = sma20 - 2 * std20
        near_bb = close <= bb_lower * bb_mult
        sigs[sym] = (rsi < rsi_thresh) & near_low & near_bb
    return sigs

zar_signals = compute_zar_signals(prices)
print(f"ZAR signals: {zar_signals.sum().sum()} events across the period")
for sym in SYMBOLS:
    n = zar_signals[sym].sum()
    print(f"  {sym}: {n} ZAR events")


# ═══════════════════════════════════════════════════════
# Strategy weight computation
# ═══════════════════════════════════════════════════════
def trend_parity_weights(date):
    """Return the weight vector for a given date using SMA+inverse-vol."""
    try:
        p = prices.loc[date]
        s = sma150.loc[date]
        v = vol40.loc[date]
    except KeyError:
        return {sym: 0 for sym in SYMBOLS}
    inv = {}
    for sym in SYMBOLS:
        if p[sym] > s[sym] and v[sym] > 0 and not np.isnan(v[sym]):
            inv[sym] = 1.0 / v[sym]
        else:
            inv[sym] = 0.0
    total = sum(inv.values())
    if total > 0:
        return {sym: inv[sym] / total for sym in SYMBOLS}
    return {sym: 0 for sym in SYMBOLS}


# ═══════════════════════════════════════════════════════
# Simulation engines
# ═══════════════════════════════════════════════════════
def simulate_lump_sum(prices, initial_capital=100000, start_date=None):
    """All capital invested at start, monthly rebalance."""
    if start_date is None:
        start_date = prices.index[SMA_WINDOW + 10]
    px = prices.loc[start_date:]

    # Identify rebalance days (first trading day of each month)
    rebal_days = []
    prev_month = None
    for d in px.index:
        if d.month != prev_month:
            rebal_days.append(d)
            prev_month = d.month

    # Track shares per symbol
    shares = {sym: 0.0 for sym in SYMBOLS}
    cash = float(initial_capital)
    equity_history = []
    total_cost = 0.0

    for d in px.index:
        # Current portfolio value
        value = cash + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)

        if d in rebal_days:
            w = trend_parity_weights(d)
            # Target value per symbol
            for sym in SYMBOLS:
                target_val = value * w[sym]
                current_val = shares[sym] * px.loc[d, sym]
                delta_val = target_val - current_val
                delta_shares = delta_val / px.loc[d, sym]
                cost = abs(delta_val) * COST_BPS / 10000
                cash -= delta_val + cost
                total_cost += cost
                shares[sym] += delta_shares
            # recompute value after rebalance
            value = cash + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)

        equity_history.append({'date': d, 'value': value, 'cash': cash,
                                'cost': total_cost})

    return pd.DataFrame(equity_history).set_index('date')


def simulate_dca(prices, monthly_budget=1000, start_date=None,
                 split=1.0, zar_signals=None):
    """
    Generic DCA engine.
    split = 1.0 → pure DCA (100% invested immediately)
    split = 0.5 → 50% immediate, 50% reserve waiting for ZAR
    """
    if start_date is None:
        start_date = prices.index[SMA_WINDOW + 10]
    px = prices.loc[start_date:]

    rebal_days = []
    prev_month = None
    for d in px.index:
        if d.month != prev_month:
            rebal_days.append(d)
            prev_month = d.month

    shares = {sym: 0.0 for sym in SYMBOLS}
    cash = 0.0                # operating cash
    reserve = 0.0             # ZAR reserve (earns BIL yield)
    total_invested = 0.0
    total_cost = 0.0
    zar_deployments = 0
    reserve_days = 0

    equity_history = []

    for d in px.index:
        # Daily reserve yield accrual
        if reserve > 0:
            reserve *= (1 + BIL_YIELD / 252)
            reserve_days += 1

        if d in rebal_days:
            # 1. Add new monthly contribution
            immediate = monthly_budget * split
            reserve_addition = monthly_budget * (1 - split)
            cash += immediate
            reserve += reserve_addition
            total_invested += monthly_budget

            # 2. Current portfolio value including new cash (excluding reserve)
            value = cash + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)

            # 3. Rebalance to target weights
            w = trend_parity_weights(d)
            for sym in SYMBOLS:
                target_val = value * w[sym]
                current_val = shares[sym] * px.loc[d, sym]
                delta_val = target_val - current_val
                cost = abs(delta_val) * COST_BPS / 10000
                cash -= delta_val + cost
                total_cost += cost
                shares[sym] += delta_val / px.loc[d, sym]

        # 4. Daily ZAR check — deploy reserve if any symbol triggers
        if zar_signals is not None and reserve > 0:
            triggered = any(zar_signals.loc[d, s] for s in SYMBOLS
                            if d in zar_signals.index)
            if triggered:
                w = trend_parity_weights(d)
                if sum(w.values()) > 0:
                    deploy_amt = reserve
                    for sym in SYMBOLS:
                        alloc = deploy_amt * w[sym]
                        cost = alloc * COST_BPS / 10000
                        shares[sym] += (alloc - cost) / px.loc[d, sym]
                        total_cost += cost
                    reserve = 0.0
                    zar_deployments += 1

        value = cash + reserve + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)
        equity_history.append({
            'date': d, 'value': value, 'cash': cash, 'reserve': reserve,
            'total_invested': total_invested, 'cost': total_cost,
        })

    df = pd.DataFrame(equity_history).set_index('date')
    df.attrs['zar_deployments'] = zar_deployments
    df.attrs['reserve_days'] = reserve_days
    return df


# ═══════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════
def twrr(values, invested=None):
    """Time-weighted return: chain daily returns computed excluding flows."""
    if invested is None:
        # Lump sum: simple compound return
        r = values.pct_change().fillna(0)
        total = (1 + r).prod() - 1
        years = (values.index[-1] - values.index[0]).days / 365.25
        return (1 + total) ** (1 / years) - 1
    else:
        # DCA: compute daily sub-period returns excluding cash flow days
        dv = values.diff()
        di = invested.diff()
        net_gain = dv - di  # gain excluding new contributions
        base = values.shift(1) + di  # base that earned the return
        r = (net_gain / base.replace(0, np.nan)).fillna(0)
        r = r.clip(-0.5, 0.5)  # sanity clip
        total = (1 + r).prod() - 1
        years = (values.index[-1] - values.index[0]).days / 365.25
        return (1 + total) ** (1 / years) - 1 if years > 0 else 0


def mwrr(values, invested):
    """Money-weighted return ≈ IRR.  Approximation: solve for constant rate."""
    # Cash flow series
    di = invested.diff().fillna(0)
    di.iloc[0] = invested.iloc[0]
    dates = values.index
    final_val = values.iloc[-1]

    def npv(r):
        total = 0.0
        for i, d in enumerate(dates):
            years = (dates[-1] - d).days / 365.25
            total += di.iloc[i] * (1 + r) ** years
        return total - final_val

    # Bisection
    lo, hi = -0.5, 2.0
    for _ in range(80):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1:
            return mid
        if v > 0:
            hi = mid
        else:
            lo = mid
    return mid


def max_dd(values):
    return ((values - values.cummax()) / values.cummax()).min()


def summarize(df, label, invested_series=None):
    values = df['value']
    if invested_series is None:
        # Lump sum
        initial = values.iloc[0]
        invested_series = pd.Series(initial, index=values.index)
        total_invested = initial
    else:
        total_invested = invested_series.iloc[-1]

    final = values.iloc[-1]
    years = (values.index[-1] - values.index[0]).days / 365.25
    tw = twrr(values, invested_series if invested_series.iloc[0] != invested_series.iloc[-1] else None)
    if invested_series.iloc[0] != invested_series.iloc[-1]:
        mw = mwrr(values, invested_series)
    else:
        mw = tw
    dd = max_dd(values)

    return {
        'label': label,
        'years': round(years, 1),
        'invested': round(total_invested, 0),
        'final': round(final, 0),
        'gain': round(final - total_invested, 0),
        'twrr': round(tw * 100, 2),
        'mwrr': round(mw * 100, 2),
        'max_dd': round(dd * 100, 2),
    }


# ═══════════════════════════════════════════════════════
# TEST 1 — Main comparison
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 1 — Lump Sum vs DCA vs DCA+ZAR (full period)")
print("="*90)

START = prices.index[SMA_WINDOW + 10]  # 2005-08 approx
MONTHLY = 1000
INITIAL_LS = 100000  # lump sum = 100k

print(f"\nPeriod: {START.date()} -> {prices.index[-1].date()}")

ls = simulate_lump_sum(prices, INITIAL_LS, START)
dca = simulate_dca(prices, MONTHLY, START, split=1.0, zar_signals=None)
zar = simulate_dca(prices, MONTHLY, START, split=0.5, zar_signals=zar_signals)

r_ls = summarize(ls, "Lump Sum (100k)")
r_dca = summarize(dca, "DCA Pur (1000€/mo)", dca['total_invested'])
r_zar = summarize(zar, "DCA+ZAR 50/50", zar['total_invested'])

print(f"\n  {'Métrique':<28s} {'Lump Sum':>12s} {'DCA Pur':>12s} {'DCA+ZAR':>12s}")
print("  " + "-"*66)
print(f"  {'Total investi':<28s} ${r_ls['invested']:>11,.0f} "
      f"${r_dca['invested']:>11,.0f} ${r_zar['invested']:>11,.0f}")
print(f"  {'Valeur finale':<28s} ${r_ls['final']:>11,.0f} "
      f"${r_dca['final']:>11,.0f} ${r_zar['final']:>11,.0f}")
print(f"  {'Gain net':<28s} ${r_ls['gain']:>11,.0f} "
      f"${r_dca['gain']:>11,.0f} ${r_zar['gain']:>11,.0f}")
print(f"  {'TWRR (annualisé)':<28s} {r_ls['twrr']:>11.2f}% "
      f"{r_dca['twrr']:>11.2f}% {r_zar['twrr']:>11.2f}%")
print(f"  {'MWRR (IRR)':<28s} {r_ls['mwrr']:>11.2f}% "
      f"{r_dca['mwrr']:>11.2f}% {r_zar['mwrr']:>11.2f}%")
print(f"  {'MaxDD valeur portefeuille':<28s} {r_ls['max_dd']:>11.2f}% "
      f"{r_dca['max_dd']:>11.2f}% {r_zar['max_dd']:>11.2f}%")

print(f"\n  ZAR statistics:")
print(f"  Nombre de déploiements ZAR : {zar.attrs['zar_deployments']}")
print(f"  Jours réserve > 0          : {zar.attrs['reserve_days']} / {len(zar)}"
      f" ({zar.attrs['reserve_days']/len(zar)*100:.0f}%)")
avg_reserve = zar['reserve'].mean()
max_reserve = zar['reserve'].max()
print(f"  Réserve moyenne            : ${avg_reserve:,.0f}")
print(f"  Réserve max                : ${max_reserve:,.0f}")
gain_zar_vs_dca = r_zar['final'] - r_dca['final']
gain_twrr = r_zar['twrr'] - r_dca['twrr']
print(f"\n  DCA+ZAR vs DCA Pur:")
print(f"    Delta valeur finale  : ${gain_zar_vs_dca:+,.0f}")
print(f"    Delta TWRR           : {gain_twrr:+.2f} pp")
print(f"    Delta MWRR           : {r_zar['mwrr']-r_dca['mwrr']:+.2f} pp")

# ═══════════════════════════════════════════════════════
# TEST 2 — Split sensitivity
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 2 — Split sensitivity (DCA+ZAR)")
print("="*90)
print(f"  {'Split':>6s} {'Final':>12s} {'TWRR':>7s} {'MWRR':>7s} "
      f"{'MaxDD':>7s} {'#ZAR':>6s} {'Avg Res':>10s}")
print("  " + "-"*60)

for split in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]:
    sim = simulate_dca(prices, MONTHLY, START, split=split,
                        zar_signals=zar_signals if split < 1.0 else None)
    s = summarize(sim, f"split={split}", sim['total_invested'])
    ndep = sim.attrs.get('zar_deployments', 0)
    avgres = sim['reserve'].mean() if 'reserve' in sim.columns else 0
    print(f"  {split:>5.1f}  ${s['final']:>11,.0f} {s['twrr']:>6.2f}% "
          f"{s['mwrr']:>6.2f}% {s['max_dd']:>6.2f}% {ndep:>5d} "
          f"${avgres:>9,.0f}")

# ═══════════════════════════════════════════════════════
# TEST 3 — ZAR condition sensitivity
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 3 — ZAR condition sensitivity (split=0.5)")
print("="*90)

configs = [
    ("Strict   (RSI<30 + near_low + bb)", 30, 0.03, 1.02, 'and'),
    ("Moderate (RSI<40 + near_low + bb)", 40, 0.03, 1.02, 'and'),
    ("Loose    (RSI<50 + (near_low|bb))", 50, 0.05, 1.05, 'or'),
]

for label, rsi_t, nl_pct, bb_m, combine in configs:
    # Build custom zar signals
    sigs = pd.DataFrame(False, index=prices.index, columns=prices.columns)
    for sym in prices.columns:
        close = prices[sym]
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - 100/(1+rs)).fillna(50)
        low20 = close.rolling(20).min()
        near_low = (close - low20) / low20 < nl_pct
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_lower = sma20 - 2 * std20
        near_bb = close <= bb_lower * bb_m
        if combine == 'and':
            sigs[sym] = (rsi < rsi_t) & near_low & near_bb
        else:
            sigs[sym] = (rsi < rsi_t) & (near_low | near_bb)
    total_sigs = sigs.sum().sum()
    sim = simulate_dca(prices, MONTHLY, START, split=0.5, zar_signals=sigs)
    s = summarize(sim, label, sim['total_invested'])
    ndep = sim.attrs['zar_deployments']
    print(f"  {label:<38s} {s['twrr']:>5.2f}%TW {s['mwrr']:>5.2f}%MW "
          f"${s['final']:>11,.0f}  sigs={total_sigs:>4d}  dep={ndep}")

# ═══════════════════════════════════════════════════════
# TEST 4 — Sub-period analysis
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 4 — Sub-period analysis")
print("="*90)

PERIODS = [
    ("P1 2006-2012 (GFC)",     "2006-01-01", "2012-12-31"),
    ("P2 2013-2019 (bull)",    "2013-01-01", "2019-12-31"),
    ("P3 2020-2026 (vol)",     "2020-01-01", "2026-12-31"),
]

for pname, s_str, e_str in PERIODS:
    start_p = max(pd.Timestamp(s_str), START)
    end_p = pd.Timestamp(e_str)
    prices_p = prices.loc[start_p:end_p]
    if len(prices_p) < 100:
        continue
    zar_p = zar_signals.loc[start_p:end_p]

    dca_p = simulate_dca(prices, MONTHLY, start_p, split=1.0)
    dca_p = dca_p.loc[:end_p]
    zar_sim = simulate_dca(prices, MONTHLY, start_p, split=0.5,
                            zar_signals=zar_signals)
    zar_sim = zar_sim.loc[:end_p]

    sd = summarize(dca_p, "DCA", dca_p['total_invested'])
    sz = summarize(zar_sim, "DCA+ZAR", zar_sim['total_invested'])
    print(f"\n  {pname}")
    print(f"    DCA       : Final ${sd['final']:>11,.0f}  "
          f"TWRR {sd['twrr']:>5.2f}%  MWRR {sd['mwrr']:>5.2f}%  "
          f"DD {sd['max_dd']:>6.2f}%")
    print(f"    DCA+ZAR   : Final ${sz['final']:>11,.0f}  "
          f"TWRR {sz['twrr']:>5.2f}%  MWRR {sz['mwrr']:>5.2f}%  "
          f"DD {sz['max_dd']:>6.2f}%")
    print(f"    Delta     : {sz['final']-sd['final']:+,.0f}  "
          f"{sz['twrr']-sd['twrr']:+.2f} pp TWRR  "
          f"{zar_sim.attrs['zar_deployments']} deployments")

# ═══════════════════════════════════════════════════════
# TEST 5 — Cash drag analysis
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 5 — Cash drag analysis")
print("="*90)

# On the main DCA+ZAR run
reserve_ts = zar['reserve']
pct_time_reserve = (reserve_ts > 0).mean() * 100
avg_reserve = reserve_ts.mean()
# Approximate opportunity cost: avg reserve × portfolio annualized return
total_years = (zar.index[-1] - zar.index[0]).days / 365.25
annual_port_ret = r_zar['twrr'] / 100
opportunity_cost = avg_reserve * annual_port_ret * total_years
# Value of ZAR benefit: gain vs DCA
zar_benefit = r_zar['final'] - r_dca['final']
print(f"\n  % du temps avec réserve > 0 : {pct_time_reserve:.1f}%")
print(f"  Réserve moyenne             : ${avg_reserve:,.0f}")
print(f"  Portfolio return annualisé  : {annual_port_ret*100:.2f}%")
print(f"  Coût d'opportunité (estim)  : ${opportunity_cost:,.0f} "
      f"sur {total_years:.1f} ans")
print(f"  Gain ZAR vs DCA (réel)      : ${zar_benefit:+,.0f}")
print(f"  Net benefit                 : ${zar_benefit - 0:+,.0f} "
      f"(coût opp déjà intégré dans l'equity curve)")

# ═══════════════════════════════════════════════════════
# CHART
# ═══════════════════════════════════════════════════════
print("\nGenerating chart...")
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10),
                                 gridspec_kw={'height_ratios': [3, 1]})

# Equity curves
ax1.plot(ls.index, ls['value'], label='Lump Sum (100k)',
         color='steelblue', lw=2)
ax1.plot(dca.index, dca['value'], label='DCA Pur',
         color='forestgreen', lw=2)
ax1.plot(zar.index, zar['value'], label='DCA+ZAR 50/50',
         color='darkorange', lw=2)
ax1.plot(dca.index, dca['total_invested'], label='Invested (DCA)',
         color='gray', lw=1, ls='--', alpha=0.7)
ax1.set_ylabel('Portfolio Value ($)')
ax1.set_title('Lump Sum vs DCA vs DCA+ZAR — Trend-Parity QQQ/TLT/GLD/VNQ')
ax1.legend(loc='upper left')
ax1.grid(alpha=0.3)

# Reserve evolution
ax2.fill_between(zar.index, zar['reserve'], 0,
                  color='darkorange', alpha=0.4, label='ZAR reserve')
ax2.set_ylabel('Cash reserve ($)')
ax2.set_xlabel('Date')
ax2.grid(alpha=0.3)
ax2.legend(loc='upper left')

fig.tight_layout()
fig.savefig('dca_comparison.png', dpi=140)
print("  → Saved dca_comparison.png")

print("\n" + "="*90)
print("  COMPLETE")
print("="*90)
