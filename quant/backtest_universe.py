"""
backtest_universe.py — Trend-Parity Universe Explorer
======================================================

Teste automatiquement toutes les combinaisons de 3 à 6 actifs
parmi un pool de candidats décorrélés, avec la logique Trend-Parity
(SMA filter + inverse-vol weighting + monthly rebalancing).

USAGE :
    pip install yfinance pandas numpy
    python backtest_universe.py

Durée : ~2-5 minutes selon le nombre de combinaisons.
Produit : rapport CSV + top 10 classement dans la console.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from itertools import combinations
import warnings
import os
import sys
from datetime import datetime

warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════

# Pool de candidats ETFs
CANDIDATES = {
    # ── Core (actuel) ──
    'QQQ':  'Nasdaq-100',
    'IEF':  'US 7-10Y Treasury',
    'GLD':  'Gold',
    # ── Equity diversification ──
    'SPY':  'S&P 500',
    'EFA':  'MSCI EAFE (Developed ex-US)',
    'EEM':  'MSCI Emerging Markets',
    'VNQ':  'US REITs',
    # ── Bonds diversification ──
    'TLT':  'US 20Y+ Treasury',
    'TIP':  'US TIPS (inflation-linked)',
    'LQD':  'US Investment Grade Corp',
    # ── Commodities ──
    'DBC':  'Commodity Index',
    'SLV':  'Silver',
}

# Paramètres de la stratégie (figés)
SMA_WINDOW = 150        # filtre de tendance
VOL_WINDOW = 40         # volatilité réalisée
LEVERAGE = 1.0          # pas de levier
INITIAL_CAPITAL = 100000
COST_PER_SIDE_BPS = 5   # 5 bps par côté

# Taille min/max de l'univers à tester
MIN_ASSETS = 3
MAX_ASSETS = 6

# Actifs obligatoires dans chaque combinaison (vide = tout tester)
REQUIRED_ASSETS = []     # ex: ['QQQ'] pour forcer QQQ dans chaque combo

# ═══════════════════════════════════════════════════════
# DOWNLOAD DES DONNÉES
# ═══════════════════════════════════════════════════════

def download_data(symbols, start='2000-01-01', end='2026-12-31'):
    """Télécharge les données adjusted close pour tous les symboles."""
    print(f"\nTéléchargement de {len(symbols)} symboles...")

    all_data = {}
    for sym in symbols:
        try:
            df = yf.download(sym, start=start, end=end,
                           auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if not df.empty and len(df) > 252:  # au moins 1 an
                all_data[sym] = df['Close']
                print(f"  ✓ {sym}: {len(df)} barres "
                      f"({df.index[0].date()} → {df.index[-1].date()})")
            else:
                print(f"  ✗ {sym}: insuffisant ({len(df)} barres)")
        except Exception as e:
            print(f"  ✗ {sym}: erreur — {e}")

    prices = pd.DataFrame(all_data)
    print(f"\n{len(prices.columns)} symboles chargés, "
          f"{len(prices)} barres daily")
    return prices

# ═══════════════════════════════════════════════════════
# STRATÉGIE TREND-PARITY
# ═══════════════════════════════════════════════════════

def trend_parity_backtest(prices, symbols, sma_window=SMA_WINDOW,
                          vol_window=VOL_WINDOW, leverage=LEVERAGE,
                          cost_bps=COST_PER_SIDE_BPS):
    """
    Backtest Trend-Parity sur un sous-ensemble de symboles.

    Logique :
    1. Chaque mois (premier jour de bourse), calculer pour chaque actif :
       - TrendOn = Close > SMA(sma_window) → binaire
       - Vol = StdDev(returns, vol_window) * sqrt(252) → annualisée
    2. Poids = Leverage × (TrendOn / Vol) / Somme(TrendOn / Vol)
    3. Appliquer les poids au portefeuille

    Retourne un dict avec toutes les métriques.
    """

    # Extraire les prix pour ce sous-ensemble
    px = prices[list(symbols)].dropna()

    if len(px) < sma_window + vol_window + 50:
        return None  # pas assez de données

    # Returns journaliers
    returns = px.pct_change()

    # SMA et Vol rolling
    sma = px.rolling(sma_window).mean()
    vol = returns.rolling(vol_window).std() * np.sqrt(252)

    # Identifier les jours de rebalancing (premier jour de chaque mois)
    px_monthly = px.copy()
    px_monthly['month'] = px_monthly.index.to_period('M')
    rebal_dates = px_monthly.groupby('month').apply(
        lambda x: x.index[0]).values
    rebal_dates = pd.DatetimeIndex(rebal_dates)

    # Filtrer les dates avec warmup suffisant
    min_date = px.index[sma_window + vol_window + 10]
    rebal_dates = rebal_dates[rebal_dates >= min_date]

    if len(rebal_dates) < 12:
        return None  # pas assez de rebalancements

    # ── Calcul des poids à chaque rebalancement ──
    weights_history = []

    for date in rebal_dates:
        if date not in px.index:
            continue

        w = {}
        inv_vols = {}

        for sym in symbols:
            trend_on = px.loc[date, sym] > sma.loc[date, sym]
            v = vol.loc[date, sym]

            if trend_on and v > 0 and not np.isnan(v):
                inv_vols[sym] = 1.0 / v
            else:
                inv_vols[sym] = 0.0

        total_inv = sum(inv_vols.values())

        if total_inv > 0:
            for sym in symbols:
                w[sym] = leverage * inv_vols[sym] / total_inv
        else:
            for sym in symbols:
                w[sym] = 0.0

        w['date'] = date
        weights_history.append(w)

    if len(weights_history) < 12:
        return None

    weights_df = pd.DataFrame(weights_history).set_index('date')

    # ── Calcul du PnL du portefeuille ──
    # Forward-fill les poids entre les rebalancements
    daily_weights = weights_df.reindex(px.index).ffill().fillna(0)

    # Ne garder que les jours où on a des poids
    start_date = weights_df.index[0]
    daily_weights = daily_weights.loc[start_date:]
    daily_returns = returns.loc[start_date:]

    # Rendement du portefeuille = somme(poids × rendement) - coûts
    port_returns = (daily_weights.shift(1) * daily_returns).sum(axis=1)

    # Coûts de transaction aux rebalancements
    weight_changes = daily_weights.diff().abs().sum(axis=1)
    turnover_cost = weight_changes * cost_bps / 10000
    port_returns = port_returns - turnover_cost

    # Equity curve
    equity = (1 + port_returns).cumprod() * INITIAL_CAPITAL

    # ── Métriques ──
    total_days = (equity.index[-1] - equity.index[0]).days
    years = total_days / 365.25

    final_equity = equity.iloc[-1]
    cagr = (final_equity / INITIAL_CAPITAL) ** (1 / years) - 1

    # Drawdown
    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd = dd.min()

    # Sharpe
    ann_return = port_returns.mean() * 252
    ann_vol = port_returns.std() * np.sqrt(252)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0

    # Calmar
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    # Turnover annuel
    annual_turnover = weight_changes.sum() / years

    # Nombre de mois en profit vs en perte
    monthly_returns = port_returns.resample('ME').sum()
    pct_positive_months = (monthly_returns > 0).mean()

    # Worst year
    annual_returns = port_returns.resample('YE').sum()
    worst_year = annual_returns.min()
    worst_year_date = annual_returns.idxmin().year
    best_year = annual_returns.max()

    # Corrélation moyenne entre les actifs (diversification)
    asset_returns = returns.loc[start_date:][list(symbols)]
    corr_matrix = asset_returns.corr()
    n = len(symbols)
    avg_corr = (corr_matrix.sum().sum() - n) / (n * (n - 1)) if n > 1 else 0

    return {
        'symbols': ','.join(sorted(symbols)),
        'n_assets': len(symbols),
        'start': equity.index[0].strftime('%Y-%m-%d'),
        'end': equity.index[-1].strftime('%Y-%m-%d'),
        'years': round(years, 1),
        'final_equity': round(final_equity, 0),
        'cagr': round(cagr * 100, 2),
        'max_dd': round(max_dd * 100, 2),
        'sharpe': round(sharpe, 2),
        'calmar': round(calmar, 2),
        'profit_factor': round(abs(monthly_returns[monthly_returns > 0].sum() /
                                   monthly_returns[monthly_returns < 0].sum()), 2)
                         if monthly_returns[monthly_returns < 0].sum() != 0 else 999,
        'pct_positive_months': round(pct_positive_months * 100, 1),
        'annual_turnover': round(annual_turnover, 2),
        'worst_year': round(worst_year * 100, 2),
        'worst_year_date': worst_year_date,
        'best_year': round(best_year * 100, 2),
        'avg_correlation': round(avg_corr, 3),
        'n_rebalances': len(weights_df),
        'equity_series': equity,  # pour export
    }

# ═══════════════════════════════════════════════════════
# MOTEUR DE TEST COMBINATOIRE
# ═══════════════════════════════════════════════════════

def run_all_combinations(prices, min_assets=MIN_ASSETS,
                         max_assets=MAX_ASSETS,
                         required=REQUIRED_ASSETS):
    """Teste toutes les combinaisons de min à max actifs."""

    available = [s for s in prices.columns if s in CANDIDATES]
    print(f"\n{'='*70}")
    print(f"BACKTEST COMBINATOIRE — Trend-Parity Universe Explorer")
    print(f"{'='*70}")
    print(f"Actifs disponibles : {available}")
    print(f"Taille univers : {min_assets} à {max_assets} actifs")
    if required:
        print(f"Actifs obligatoires : {required}")

    results = []
    total_combos = 0

    for n in range(min_assets, max_assets + 1):
        if required:
            # Filtrer les combos qui contiennent les actifs obligatoires
            optional = [s for s in available if s not in required]
            n_optional = n - len(required)
            if n_optional < 0:
                continue
            combos = [tuple(sorted(list(required) + list(c)))
                     for c in combinations(optional, n_optional)]
        else:
            combos = [tuple(sorted(c)) for c in combinations(available, n)]

        total_combos += len(combos)

    print(f"Combinaisons à tester : {total_combos}")
    print(f"{'='*70}\n")

    tested = 0
    for n in range(min_assets, max_assets + 1):
        if required:
            optional = [s for s in available if s not in required]
            n_optional = n - len(required)
            if n_optional < 0:
                continue
            combos = [tuple(sorted(list(required) + list(c)))
                     for c in combinations(optional, n_optional)]
        else:
            combos = [tuple(sorted(c)) for c in combinations(available, n)]

        for combo in combos:
            tested += 1
            result = trend_parity_backtest(prices, list(combo))

            if result is not None:
                # Ne pas stocker l'equity series dans le CSV
                result_clean = {k: v for k, v in result.items()
                               if k != 'equity_series'}
                results.append(result_clean)

                status = f"CAGR={result['cagr']:6.2f}%  " \
                         f"DD={result['max_dd']:6.2f}%  " \
                         f"Sharpe={result['sharpe']:.2f}"
            else:
                status = "SKIP (insuffisant)"

            # Progress
            if tested % 10 == 0 or tested == total_combos:
                print(f"  [{tested}/{total_combos}] "
                      f"{','.join(combo):40s} → {status}")

    return pd.DataFrame(results)

# ═══════════════════════════════════════════════════════
# ANALYSE DES RÉSULTATS
# ═══════════════════════════════════════════════════════

def analyze_results(df):
    """Analyse et affiche les meilleurs résultats."""

    if df.empty:
        print("\nAucun résultat valide !")
        return

    print(f"\n{'='*70}")
    print(f"RÉSULTATS — {len(df)} combinaisons testées")
    print(f"{'='*70}")

    # ── Top 10 par Sharpe ──
    print(f"\n{'─'*70}")
    print(f"TOP 10 PAR SHARPE RATIO")
    print(f"{'─'*70}")
    top_sharpe = df.nlargest(10, 'sharpe')
    for i, row in top_sharpe.iterrows():
        print(f"  {row['sharpe']:.2f} Sharpe | "
              f"CAGR {row['cagr']:5.1f}% | "
              f"DD {row['max_dd']:6.1f}% | "
              f"Calmar {row['calmar']:.2f} | "
              f"PF {row['profit_factor']:.1f} | "
              f"Corr {row['avg_correlation']:.2f} | "
              f"{row['symbols']}")

    # ── Top 10 par CAGR ──
    print(f"\n{'─'*70}")
    print(f"TOP 10 PAR CAGR")
    print(f"{'─'*70}")
    top_cagr = df.nlargest(10, 'cagr')
    for i, row in top_cagr.iterrows():
        print(f"  CAGR {row['cagr']:5.1f}% | "
              f"DD {row['max_dd']:6.1f}% | "
              f"Sharpe {row['sharpe']:.2f} | "
              f"Calmar {row['calmar']:.2f} | "
              f"{row['symbols']}")

    # ── Top 10 par Calmar (CAGR/MaxDD) ──
    print(f"\n{'─'*70}")
    print(f"TOP 10 PAR CALMAR (CAGR / |MaxDD|)")
    print(f"{'─'*70}")
    top_calmar = df.nlargest(10, 'calmar')
    for i, row in top_calmar.iterrows():
        print(f"  Calmar {row['calmar']:.2f} | "
              f"CAGR {row['cagr']:5.1f}% | "
              f"DD {row['max_dd']:6.1f}% | "
              f"Sharpe {row['sharpe']:.2f} | "
              f"{row['symbols']}")

    # ── Top 10 meilleur DD ──
    print(f"\n{'─'*70}")
    print(f"TOP 10 PAR PLUS FAIBLE DRAWDOWN")
    print(f"{'─'*70}")
    top_dd = df.nlargest(10, 'max_dd')  # max_dd is negative, largest = closest to 0
    for i, row in top_dd.iterrows():
        print(f"  DD {row['max_dd']:6.1f}% | "
              f"CAGR {row['cagr']:5.1f}% | "
              f"Sharpe {row['sharpe']:.2f} | "
              f"{row['symbols']}")

    # ── Comparaison par taille d'univers ──
    print(f"\n{'─'*70}")
    print(f"MOYENNE PAR TAILLE D'UNIVERS")
    print(f"{'─'*70}")
    for n in sorted(df['n_assets'].unique()):
        sub = df[df['n_assets'] == n]
        print(f"  {n} actifs ({len(sub):3d} combos) : "
              f"CAGR {sub['cagr'].mean():5.1f}% ± {sub['cagr'].std():4.1f} | "
              f"DD {sub['max_dd'].mean():6.1f}% | "
              f"Sharpe {sub['sharpe'].mean():.2f} | "
              f"Corr {sub['avg_correlation'].mean():.2f}")

    # ── Fréquence d'apparition dans le top 20 Sharpe ──
    print(f"\n{'─'*70}")
    print(f"ACTIFS LES PLUS FRÉQUENTS DANS LE TOP 20 SHARPE")
    print(f"{'─'*70}")
    top20 = df.nlargest(20, 'sharpe')
    from collections import Counter
    all_syms = []
    for syms in top20['symbols']:
        all_syms.extend(syms.split(','))
    counts = Counter(all_syms)
    for sym, count in counts.most_common():
        bar = '█' * count
        print(f"  {sym:5s} : {count:2d}/20  {bar}")

    # ── Le combo original (QQQ, IEF, GLD) comme baseline ──
    baseline_key = ','.join(sorted(['QQQ', 'IEF', 'GLD']))
    baseline = df[df['symbols'] == baseline_key]
    if not baseline.empty:
        b = baseline.iloc[0]
        print(f"\n{'─'*70}")
        print(f"BASELINE (QQQ, IEF, GLD)")
        print(f"{'─'*70}")
        print(f"  CAGR={b['cagr']:.1f}%  DD={b['max_dd']:.1f}%  "
              f"Sharpe={b['sharpe']:.2f}  Calmar={b['calmar']:.2f}  "
              f"PF={b['profit_factor']:.1f}")

# ═══════════════════════════════════════════════════════
# EXPORT DES MEILLEURS EQUITY CURVES
# ═══════════════════════════════════════════════════════

def export_top_equity_curves(prices, df, top_n=5):
    """Re-run et exporte les equity curves des top combos."""

    top = df.nlargest(top_n, 'sharpe')
    curves = {}

    for _, row in top.iterrows():
        symbols = row['symbols'].split(',')
        result = trend_parity_backtest(prices, symbols)
        if result and 'equity_series' in result:
            key = row['symbols']
            curves[key] = result['equity_series']

    if curves:
        eq_df = pd.DataFrame(curves)
        eq_df.to_csv('top_equity_curves.csv')
        print(f"\nEquity curves exportées → top_equity_curves.csv")

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 70)
    print("  TREND-PARITY UNIVERSE EXPLORER")
    print(f"  SMA={SMA_WINDOW}  Vol={VOL_WINDOW}  "
          f"Leverage={LEVERAGE}  Cost={COST_PER_SIDE_BPS}bps/side")
    print("=" * 70)

    # 1. Download
    prices = download_data(list(CANDIDATES.keys()))

    if len(prices.columns) < MIN_ASSETS:
        print(f"\nERREUR: seulement {len(prices.columns)} symboles chargés, "
              f"besoin de {MIN_ASSETS} minimum.")
        sys.exit(1)

    # 2. Corrélation du pool complet
    print(f"\n{'─'*70}")
    print("MATRICE DE CORRÉLATION DU POOL (returns daily)")
    print(f"{'─'*70}")
    corr = prices.pct_change().corr().round(2)
    print(corr.to_string())

    # 3. Run toutes les combinaisons
    results_df = run_all_combinations(prices)

    # 4. Analyser
    analyze_results(results_df)

    # 5. Export CSV
    output_file = 'trend_parity_universe_results.csv'
    results_df.to_csv(output_file, index=False)
    print(f"\nRésultats complets → {output_file}")

    # 6. Export equity curves top 5
    export_top_equity_curves(prices, results_df, top_n=5)

    print(f"\n{'='*70}")
    print("  TERMINÉ")
    print(f"{'='*70}")
