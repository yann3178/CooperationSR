"""
dca_zar_full.py — Lump Sum vs DCA vs DCA+ZAR (Tradosaure spec)
================================================================

Full ZAR spec: cluster of local minima + volume confirmation + non-break.

Because detect_zar_levels is expensive, we precompute a daily table of
"is any symbol in ZAR ACTIVE or SURVEILLER" booleans once at the start.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

SYMBOLS = ['QQQ', 'TLT', 'GLD', 'VNQ']
SMA_WINDOW = 150
VOL_WINDOW = 40
COST_BPS = 5
BIL_YIELD = 0.02
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data_ohlcv')


# ═══════════════════════════════════════════════════════
# Load OHLCV data
# ═══════════════════════════════════════════════════════
def load_ohlcv(sym):
    df = pd.read_csv(f'{DATA_DIR}/{sym}.csv', skiprows=[1, 2],
                     parse_dates=[0], index_col=0)
    # Ensure columns
    df = df.rename(columns=lambda c: c.strip())
    return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)


print("Loading OHLCV data...")
ohlcv = {s: load_ohlcv(s) for s in SYMBOLS}
for s in SYMBOLS:
    print(f"  {s}: {ohlcv[s].index[0].date()} -> {ohlcv[s].index[-1].date()} "
          f"({len(ohlcv[s])} rows)")

# Shared close price frame aligned
close_px = pd.concat({s: ohlcv[s]['Close'] for s in SYMBOLS}, axis=1)
close_px = close_px.dropna()
print(f"Common window: {close_px.index[0].date()} -> {close_px.index[-1].date()}")


# ═══════════════════════════════════════════════════════
# ZAR detection — full Tradosaure spec
# ═══════════════════════════════════════════════════════
def detect_zar_levels(df: pd.DataFrame, end_idx: int, window: int = 20,
                      min_touches: int = 2, lookback_bars: int = 500):
    """
    Detect all active ZAR levels for a symbol at end_idx.

    Parameters
    ----------
    df : OHLCV dataframe
    end_idx : last index to look at (exclusive of future data)
    window : base window for local minima / non-break check
    min_touches : minimum touches required for a cluster
    lookback_bars : how far back to scan for local minima

    Returns a list of dicts — one per valid ZAR level.
    """
    start_idx = max(0, end_idx - lookback_bars)
    data = df.iloc[start_idx:end_idx + 1]
    if len(data) < window * 2 + 20:
        return []

    lows = data['Low'].values
    closes = data['Close'].values
    volumes = data['Volume'].values
    n = len(data)

    # Dynamic tolerance: 0.5× rolling std normalised, bounded 1%-5%
    std_norm = np.std(closes[-20:]) / closes[-1] if closes[-1] > 0 else 0
    tolerance = max(0.01, min(0.05, std_norm * 0.5))

    # Dynamic window: grow with ATR-based vol
    atr_raw = np.mean(np.abs(np.diff(lows[-14:]))) if n >= 14 else 0
    volatility = atr_raw / closes[-1] if closes[-1] > 0 else 0.01
    dyn_window = max(5, int(window + volatility * 50))

    if n < dyn_window * 2 + 10:
        return []

    # 1. Local minima: lows[i] == min of [i-dyn_window:i+dyn_window+1]
    local_mins = []
    for i in range(dyn_window, n - dyn_window):
        w_min = lows[i - dyn_window:i + dyn_window + 1].min()
        if lows[i] == w_min:
            local_mins.append((i, lows[i]))

    if not local_mins:
        return []

    # 2. Cluster by tolerance
    clusters = {}
    for idx, price in local_mins:
        matched = False
        for cprice in list(clusters.keys()):
            if abs(price - cprice) / cprice <= tolerance:
                clusters[cprice].append((idx, price))
                matched = True
                break
        if not matched:
            clusters[price] = [(idx, price)]

    # Volume MA20 for confirmation
    vol_ma20 = pd.Series(volumes).rolling(20).mean().values

    zar_levels = []
    current_price = closes[-1]
    recent_lows = lows[-dyn_window:]
    recent_closes = closes[-dyn_window:]

    for cprice, touches in clusters.items():
        if len(touches) < min_touches:
            continue

        avg_price = np.mean([t[1] for t in touches])
        low_broken = (recent_lows < avg_price * (1 - tolerance))
        close_broken = (recent_closes < avg_price * (1 - tolerance))
        if (low_broken & close_broken).any():
            continue

        vol_confirmed = 0
        vol_strengths = []
        for tidx, _ in touches:
            if tidx < len(vol_ma20) and not np.isnan(vol_ma20[tidx]) \
                    and vol_ma20[tidx] > 0:
                ratio = volumes[tidx] / vol_ma20[tidx]
                vol_strengths.append(ratio)
                if ratio > 1.2:
                    vol_confirmed += 1
        if vol_confirmed == 0:
            continue

        distance_pct = (current_price - avg_price) / avg_price * 100
        if distance_pct <= 2:
            status = 'ZONE_ACHAT_ACTIVE'
        elif distance_pct <= 5:
            status = 'SURVEILLER'
        elif distance_pct <= 15:
            status = 'ATTENDRE'
        else:
            status = 'TROP_LOIN'

        zar_levels.append({
            'price': avg_price,
            'touches': len(touches),
            'vol_strength': float(np.mean(vol_strengths)) if vol_strengths else 0,
            'distance_pct': distance_pct,
            'status': status,
        })

    zar_levels.sort(key=lambda z: (z['touches'], z['vol_strength']),
                    reverse=True)
    return zar_levels


def precompute_zar_table(ohlcv_dict, window=20, min_touches=2,
                         distance_max=5.0, step=1):
    """
    Precompute, for each trading day in the common window, whether each
    symbol has an active ZAR (distance ≤ distance_max).

    Returns a DataFrame indexed by date, columns = symbols, values = bool.
    """
    dates = close_px.index
    result = pd.DataFrame(False, index=dates, columns=list(ohlcv_dict.keys()))

    # Need a burn-in of ~500 bars for detection
    min_required = 500

    for sym in ohlcv_dict:
        df = ohlcv_dict[sym]
        print(f"  Precomputing ZAR for {sym}...", end=' ', flush=True)
        sym_dates = df.index
        last_status = False
        zar_count = 0
        # Build a map from each date in our result index to df index
        for i, d in enumerate(dates):
            # Skip first bars
            try:
                df_idx = df.index.get_loc(d)
            except KeyError:
                result.iloc[i, result.columns.get_loc(sym)] = last_status
                continue
            if df_idx < min_required:
                continue
            if i % step != 0:
                # Use previous value to speed up (ZAR status is sticky)
                result.iloc[i, result.columns.get_loc(sym)] = last_status
                continue
            zlevels = detect_zar_levels(df, df_idx, window, min_touches,
                                         lookback_bars=500)
            active = any(z['status'] in ('ZONE_ACHAT_ACTIVE', 'SURVEILLER')
                         and z['distance_pct'] <= distance_max
                         for z in zlevels)
            result.iloc[i, result.columns.get_loc(sym)] = active
            last_status = active
            if active:
                zar_count += 1
        print(f"{zar_count} active days")

    return result


# ═══════════════════════════════════════════════════════
# Trend-Parity weights
# ═══════════════════════════════════════════════════════
sma150 = close_px.rolling(SMA_WINDOW).mean()
vol40 = close_px.pct_change().rolling(VOL_WINDOW).std() * np.sqrt(252)


def tp_weights(date):
    try:
        p = close_px.loc[date]
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
# Simulation engines (same as dca_comparison.py)
# ═══════════════════════════════════════════════════════
def simulate_lump_sum(initial_capital=100000, start_date=None):
    if start_date is None:
        start_date = close_px.index[SMA_WINDOW + 10]
    px = close_px.loc[start_date:]
    rebal_days = set()
    prev_month = None
    for d in px.index:
        if d.month != prev_month:
            rebal_days.add(d)
            prev_month = d.month
    shares = {s: 0.0 for s in SYMBOLS}
    cash = float(initial_capital)
    hist = []
    for d in px.index:
        if d in rebal_days:
            value = cash + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)
            w = tp_weights(d)
            for sym in SYMBOLS:
                target = value * w[sym]
                cur = shares[sym] * px.loc[d, sym]
                dv = target - cur
                cost = abs(dv) * COST_BPS / 10000
                cash -= dv + cost
                shares[sym] += dv / px.loc[d, sym]
        value = cash + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)
        hist.append({'date': d, 'value': value, 'invested': initial_capital})
    return pd.DataFrame(hist).set_index('date')


def simulate_dca(monthly_budget=1000, split=1.0, zar_signals=None,
                 start_date=None):
    if start_date is None:
        start_date = close_px.index[SMA_WINDOW + 10]
    px = close_px.loc[start_date:]
    rebal_days = set()
    prev_month = None
    for d in px.index:
        if d.month != prev_month:
            rebal_days.add(d)
            prev_month = d.month

    shares = {s: 0.0 for s in SYMBOLS}
    cash = 0.0
    reserve = 0.0
    invested = 0.0
    deployments = 0
    reserve_days = 0
    hist = []

    for d in px.index:
        if reserve > 0:
            reserve *= (1 + BIL_YIELD / 252)
            reserve_days += 1

        if d in rebal_days:
            cash += monthly_budget * split
            reserve += monthly_budget * (1 - split)
            invested += monthly_budget
            value = cash + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)
            w = tp_weights(d)
            for sym in SYMBOLS:
                target = value * w[sym]
                cur = shares[sym] * px.loc[d, sym]
                dv = target - cur
                cost = abs(dv) * COST_BPS / 10000
                cash -= dv + cost
                shares[sym] += dv / px.loc[d, sym]

        # Daily ZAR check
        if zar_signals is not None and reserve > 0:
            triggered = False
            if d in zar_signals.index:
                triggered = bool(zar_signals.loc[d].any())
            if triggered:
                w = tp_weights(d)
                if sum(w.values()) > 0:
                    deploy = reserve
                    for sym in SYMBOLS:
                        alloc = deploy * w[sym]
                        cost = alloc * COST_BPS / 10000
                        shares[sym] += (alloc - cost) / px.loc[d, sym]
                    reserve = 0.0
                    deployments += 1

        value = cash + reserve + sum(shares[s] * px.loc[d, s] for s in SYMBOLS)
        hist.append({'date': d, 'value': value, 'cash': cash,
                      'reserve': reserve, 'invested': invested})

    df = pd.DataFrame(hist).set_index('date')
    df.attrs['deployments'] = deployments
    df.attrs['reserve_days'] = reserve_days
    return df


# ═══════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════
def twrr(values, invested):
    dv = values.diff()
    di = invested.diff().fillna(0)
    base = values.shift(1) + di
    gain = (dv - di) / base.replace(0, np.nan)
    gain = gain.fillna(0).clip(-0.5, 0.5)
    total = (1 + gain).prod() - 1
    years = (values.index[-1] - values.index[0]).days / 365.25
    return (1 + total) ** (1 / years) - 1 if years > 0 else 0


def mwrr(values, invested):
    """Bisection IRR on cash flows."""
    di = invested.diff().fillna(0)
    di.iloc[0] = invested.iloc[0]
    final = values.iloc[-1]
    dates = values.index
    total_years = (dates[-1] - dates[0]).days / 365.25
    if total_years == 0:
        return 0

    def npv(r):
        t = 0.0
        for i in range(len(dates)):
            yrs = (dates[-1] - dates[i]).days / 365.25
            t += di.iloc[i] * (1 + r) ** yrs
        return t - final

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
    return float(((values - values.cummax()) / values.cummax()).min())


def summarize(df, label, is_lump=False):
    values = df['value']
    if is_lump:
        invested = pd.Series(values.iloc[0], index=values.index)
        tw = values.pct_change().dropna()
        total = (1 + tw).prod() - 1
        years = (values.index[-1] - values.index[0]).days / 365.25
        tw_ann = (1 + total) ** (1 / years) - 1
        mw_ann = tw_ann
    else:
        invested = df['invested']
        tw_ann = twrr(values, invested)
        mw_ann = mwrr(values, invested)
    dd = max_dd(values)
    return {
        'label': label,
        'invested': invested.iloc[-1],
        'final': values.iloc[-1],
        'twrr': tw_ann * 100,
        'mwrr': mw_ann * 100,
        'max_dd': dd * 100,
    }


# ═══════════════════════════════════════════════════════
# Precompute ZAR signals
# ═══════════════════════════════════════════════════════
print("\nPrecomputing ZAR signals (this takes ~1-2 minutes)...")
zar_moderate = precompute_zar_table(ohlcv, window=20, min_touches=2,
                                     distance_max=5.0)
zar_moderate.to_csv('zar_signals_moderate.csv')
total_active_days = zar_moderate.any(axis=1).sum()
print(f"  Total days with ≥1 symbol in active ZAR: "
      f"{total_active_days} ({total_active_days/len(zar_moderate)*100:.1f}%)")
for sym in SYMBOLS:
    n = zar_moderate[sym].sum()
    print(f"    {sym}: {n} active days ({n/len(zar_moderate)*100:.1f}%)")

# ═══════════════════════════════════════════════════════
# TEST 1 — Main comparison
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 1 — Lump Sum vs DCA vs DCA+ZAR (full period)")
print("="*90)

START = close_px.index[SMA_WINDOW + 10]
print(f"Period: {START.date()} -> {close_px.index[-1].date()}")

ls = simulate_lump_sum(100000, START)
dca = simulate_dca(1000, split=1.0, zar_signals=None, start_date=START)
zar = simulate_dca(1000, split=0.5, zar_signals=zar_moderate, start_date=START)

r_ls = summarize(ls, "Lump Sum 100k", is_lump=True)
r_dca = summarize(dca, "DCA pur")
r_zar = summarize(zar, "DCA+ZAR 50/50")

print(f"\n  {'Metric':<30s} {'Lump Sum':>14s} {'DCA pur':>14s} {'DCA+ZAR':>14s}")
print("  " + "-"*72)
print(f"  {'Total invested':<30s} ${r_ls['invested']:>13,.0f} "
      f"${r_dca['invested']:>13,.0f} ${r_zar['invested']:>13,.0f}")
print(f"  {'Final value':<30s} ${r_ls['final']:>13,.0f} "
      f"${r_dca['final']:>13,.0f} ${r_zar['final']:>13,.0f}")
print(f"  {'Gain':<30s} ${r_ls['final']-r_ls['invested']:>13,.0f} "
      f"${r_dca['final']-r_dca['invested']:>13,.0f} "
      f"${r_zar['final']-r_zar['invested']:>13,.0f}")
print(f"  {'TWRR (annualised)':<30s} {r_ls['twrr']:>13.2f}% "
      f"{r_dca['twrr']:>13.2f}% {r_zar['twrr']:>13.2f}%")
print(f"  {'MWRR (IRR)':<30s} {r_ls['mwrr']:>13.2f}% "
      f"{r_dca['mwrr']:>13.2f}% {r_zar['mwrr']:>13.2f}%")
print(f"  {'MaxDD':<30s} {r_ls['max_dd']:>13.2f}% "
      f"{r_dca['max_dd']:>13.2f}% {r_zar['max_dd']:>13.2f}%")

print(f"\n  ZAR statistics:")
print(f"    Deployments             : {zar.attrs['deployments']}")
print(f"    Reserve days > 0        : {zar.attrs['reserve_days']} / {len(zar)} "
      f"({zar.attrs['reserve_days']/len(zar)*100:.0f}%)")
print(f"    Avg reserve             : ${zar['reserve'].mean():,.0f}")
print(f"    Max reserve             : ${zar['reserve'].max():,.0f}")

gain_zar = r_zar['final'] - r_dca['final']
delta_tw = r_zar['twrr'] - r_dca['twrr']
delta_mw = r_zar['mwrr'] - r_dca['mwrr']
print(f"\n  DCA+ZAR vs DCA pur:")
print(f"    Δ final          : ${gain_zar:+,.0f}")
print(f"    Δ TWRR           : {delta_tw:+.3f} pp ({delta_tw*100:+.1f} bps)")
print(f"    Δ MWRR           : {delta_mw:+.3f} pp ({delta_mw*100:+.1f} bps)")

# ═══════════════════════════════════════════════════════
# TEST 2 — Split sensitivity
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 2 — Split sensitivity")
print("="*90)
print(f"  {'Split':>6s} {'Final':>14s} {'TWRR':>7s} {'MWRR':>7s} "
      f"{'MaxDD':>7s} {'#ZAR':>6s} {'AvgRes':>10s}")
print("  " + "-"*65)
split_results = []
for sp in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]:
    sig = zar_moderate if sp < 1.0 else None
    sim = simulate_dca(1000, split=sp, zar_signals=sig, start_date=START)
    s = summarize(sim, f"s={sp}")
    split_results.append(s)
    ndep = sim.attrs.get('deployments', 0)
    avg_res = sim['reserve'].mean() if 'reserve' in sim.columns else 0
    print(f"  {sp:>5.1f}  ${s['final']:>13,.0f} {s['twrr']:>6.2f}% "
          f"{s['mwrr']:>6.2f}% {s['max_dd']:>6.2f}% {ndep:>5d} "
          f"${avg_res:>9,.0f}")

# ═══════════════════════════════════════════════════════
# TEST 3 — ZAR sensitivity
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 3 — ZAR condition sensitivity (split=0.5)")
print("="*90)

configs = [
    ("Strict   (touches≥3, dist≤2%)", 3, 2.0),
    ("Moderate (touches≥2, dist≤5%)", 2, 5.0),
    ("Loose    (touches≥1, dist≤10%)", 1, 10.0),
]
print(f"\n  {'Config':<35s} {'Active%':>8s} {'#Dep':>5s} "
      f"{'Final':>14s} {'TWRR':>7s} {'MWRR':>7s}")
print("  " + "-"*75)
for label, mt, dmax in configs:
    z_table = precompute_zar_table(ohlcv, window=20, min_touches=mt,
                                    distance_max=dmax)
    active_pct = z_table.any(axis=1).mean() * 100
    sim = simulate_dca(1000, split=0.5, zar_signals=z_table, start_date=START)
    s = summarize(sim, label)
    ndep = sim.attrs['deployments']
    print(f"  {label:<35s} {active_pct:>7.1f}% {ndep:>5d} "
          f"${s['final']:>13,.0f} {s['twrr']:>6.2f}% {s['mwrr']:>6.2f}%")

# ═══════════════════════════════════════════════════════
# TEST 4 — Sub-periods
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 4 — Sub-period analysis")
print("="*90)

periods = [
    ("P1 2006-2012 (GFC)",  "2006-01-01", "2012-12-31"),
    ("P2 2013-2019 (bull)", "2013-01-01", "2019-12-31"),
    ("P3 2020-2026 (vol)",  "2020-01-01", "2026-12-31"),
]

for pname, s_str, e_str in periods:
    start_p = max(pd.Timestamp(s_str), START)
    end_p = pd.Timestamp(e_str)
    if start_p >= close_px.index[-1]:
        continue
    dca_p = simulate_dca(1000, split=1.0, start_date=start_p).loc[:end_p]
    zar_p = simulate_dca(1000, split=0.5, zar_signals=zar_moderate,
                          start_date=start_p).loc[:end_p]
    sd = summarize(dca_p, "DCA")
    sz = summarize(zar_p, "DCA+ZAR")
    print(f"\n  {pname}")
    print(f"    DCA       : final ${sd['final']:>12,.0f}  "
          f"TWRR {sd['twrr']:>5.2f}%  MWRR {sd['mwrr']:>5.2f}%  "
          f"DD {sd['max_dd']:>6.2f}%")
    print(f"    DCA+ZAR   : final ${sz['final']:>12,.0f}  "
          f"TWRR {sz['twrr']:>5.2f}%  MWRR {sz['mwrr']:>5.2f}%  "
          f"DD {sz['max_dd']:>6.2f}%   deploys={zar_p.attrs['deployments']}")
    print(f"    Δ         : {sz['final']-sd['final']:+,.0f}  "
          f"TWRR {sz['twrr']-sd['twrr']:+.2f} pp")

# ═══════════════════════════════════════════════════════
# TEST 5 — Cash drag
# ═══════════════════════════════════════════════════════
print("\n" + "="*90)
print("TEST 5 — Cash drag analysis")
print("="*90)
reserve_ts = zar['reserve']
pct = (reserve_ts > 0).mean() * 100
avg_res = reserve_ts.mean()
years = (zar.index[-1] - zar.index[0]).days / 365.25
port_ret = r_zar['twrr'] / 100
opp_cost_total = avg_res * port_ret * years
print(f"  % days reserve > 0        : {pct:.1f}%")
print(f"  Avg reserve               : ${avg_res:,.0f}")
print(f"  Portfolio annual return   : {port_ret*100:.2f}%")
print(f"  Estimated opportunity cost: ${opp_cost_total:,.0f} over {years:.1f}y")
print(f"  Actual DCA+ZAR - DCA pur  : ${gain_zar:+,.0f}")
bars_total = len(zar)
triggered_bars = (zar_moderate.any(axis=1) & (reserve_ts > 0)).sum()
print(f"  Days reserve deployable   : {triggered_bars}")

# ═══════════════════════════════════════════════════════
# Chart
# ═══════════════════════════════════════════════════════
print("\nGenerating chart...")
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10),
                                 gridspec_kw={'height_ratios': [3, 1]})
ax1.plot(ls.index, ls['value'], label='Lump Sum (100k)',
         color='steelblue', lw=2)
ax1.plot(dca.index, dca['value'], label='DCA pur',
         color='forestgreen', lw=2)
ax1.plot(zar.index, zar['value'], label='DCA+ZAR 50/50 (full spec)',
         color='darkorange', lw=2)
ax1.plot(dca.index, dca['invested'], label='Cumul invested (DCA)',
         color='gray', lw=1, ls='--', alpha=0.7)
ax1.set_ylabel('Portfolio value ($)')
ax1.set_title('Lump Sum vs DCA vs DCA+ZAR (Tradosaure full spec) — '
              'Trend-Parity QQQ/TLT/GLD/VNQ')
ax1.legend(loc='upper left')
ax1.grid(alpha=0.3)

ax2.fill_between(zar.index, zar['reserve'], 0, color='darkorange',
                  alpha=0.4, label='ZAR reserve')
ax2.set_ylabel('Cash reserve ($)')
ax2.set_xlabel('Date')
ax2.grid(alpha=0.3)
ax2.legend(loc='upper left')

fig.tight_layout()
fig.savefig('dca_zar_full_chart.png', dpi=140)
print("  → Saved dca_zar_full_chart.png")

print("\n" + "="*90)
print("  COMPLETE")
print("="*90)
