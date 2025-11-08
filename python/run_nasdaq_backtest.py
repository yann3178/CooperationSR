#!/usr/bin/env python3
"""
Backtest sur Nasdaq (QQQ) - Script de démonstration

Ce script télécharge les données QQQ et exécute un backtest complet
avec la stratégie Renko Trend Following.

Usage:
    python run_nasdaq_backtest.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import pandas as pd
import numpy as np
from datetime import datetime

from backtest import Backtest
from strategy import StrategyConfig

print("=" * 70)
print("RENKO TREND FOLLOWING - BACKTEST NASDAQ (QQQ)")
print("=" * 70)
print()

# Télécharger les données QQQ
print("[1/4] Téléchargement des données QQQ...")
print("-" * 70)

try:
    import yfinance as yf

    # Télécharger QQQ depuis 2010
    ticker = yf.Ticker("QQQ")
    df = ticker.history(start="2010-01-01", end="2024-12-31")

    if df.empty:
        raise ValueError("Aucune donnée téléchargée")

    print(f"✓ Téléchargé {len(df)} barres")
    print(f"  Période: {df.index[0].date()} à {df.index[-1].date()}")
    print(f"  Prix: ${df['Close'].iloc[0]:.2f} → ${df['Close'].iloc[-1]:.2f}")
    print(f"  Performance Buy-Hold: {((df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1) * 100:.2f}%")

    # Sauvegarder les données
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    data_file = data_dir / 'QQQ_2010_2024.csv'
    df.to_csv(data_file)
    print(f"  Sauvegardé: {data_file}")

except ImportError:
    print("⚠️  yfinance non installé, utilisation de données simulées...")
    print()

    # Créer des données simulées basées sur QQQ
    np.random.seed(42)
    dates = pd.date_range('2010-01-01', '2024-12-31', freq='D')

    # Simuler une tendance haussière similaire à QQQ (environ +300% sur la période)
    n_days = len(dates)
    trend = np.linspace(50, 400, n_days)  # De $50 à $400
    volatility = 3.0
    noise = np.random.randn(n_days) * volatility

    # Créer un mouvement plus réaliste avec des tendances
    price_changes = np.random.randn(n_days) * volatility + 0.03  # Slight upward bias
    prices = 50 * np.exp(np.cumsum(price_changes / 100))

    df = pd.DataFrame({
        'Open': prices + np.random.randn(n_days) * 1,
        'High': prices + np.abs(np.random.randn(n_days) * 3),
        'Low': prices - np.abs(np.random.randn(n_days) * 3),
        'Close': prices,
        'Volume': np.random.randint(30000000, 100000000, n_days)
    }, index=dates)

    # Garder seulement les jours de semaine
    df = df[df.index.dayofweek < 5]

    print(f"✓ Créé {len(df)} barres de données simulées (type QQQ)")
    print(f"  Période: {df.index[0].date()} à {df.index[-1].date()}")
    print(f"  Prix: ${df['Close'].iloc[0]:.2f} → ${df['Close'].iloc[-1]:.2f}")
    print(f"  Performance simulée: {((df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1) * 100:.2f}%")

print()

# Préparer les données
price_data = df.copy()
price_data.columns = price_data.columns.str.lower()

# Configuration de la stratégie (Conservative Long-Only)
print("[2/4] Configuration de la stratégie...")
print("-" * 70)

config = StrategyConfig(
    # Trend Filter
    use_trend_filter=True,
    trend_sma_period=200,
    trend_margin=0.00,

    # Entry
    entry_confirm_type="FIRST_GREEN",
    require_no_wick=False,
    require_prior_red=True,

    # Direction
    allow_long=True,
    allow_short=False,
    short_trend_filter=True,

    # Position Sizing
    position_size_type="PERCENT_EQUITY",
    position_size_value=0.90,
    initial_capital=30000,

    # Exit
    stop_type="PREVIOUS_BRICK",
    stop_intraday=True,
    stop_trail=True,
    exit_on_reverse_brick=True
)

print("Configuration:")
print(f"  Capital initial:        ${config.initial_capital:,.2f}")
print(f"  Position size:          {config.position_size_value * 100:.0f}% de l'équité")
print(f"  Filtre de tendance:     SMA({config.trend_sma_period})")
print(f"  Type de brique Renko:   PERCENTAGE")
print(f"  Taille de brique:       1.0% (0.01)")
print(f"  Confirmation d'entrée:  {config.entry_confirm_type}")
print(f"  Direction:              LONG uniquement")
print(f"  Trailing stop:          Activé")
print()

# Exécuter le backtest
print("[3/4] Exécution du backtest...")
print("-" * 70)

backtest = Backtest(
    price_data=price_data,
    strategy_config=config,
    brick_type="PERCENTAGE",
    brick_size=0.01,  # 1%
    atr_period=14
)

summary = backtest.run()

# Afficher les résultats
print()
print("[4/4] Résultats du backtest...")
print("-" * 70)
print()

backtest.print_report()

# Afficher les trades
print()
print("=" * 70)
print("HISTORIQUE DES TRADES")
print("=" * 70)
print()

trades_df = backtest.trades_df

if not trades_df.empty:
    # Afficher un résumé des trades
    print(f"Total trades: {len(trades_df)}")
    print()

    # Top 5 meilleurs trades
    print("🏆 Top 5 meilleurs trades:")
    print("-" * 70)
    top_trades = trades_df.nlargest(5, 'pnl')[['entry_date', 'exit_date', 'entry_price', 'exit_price', 'pnl', 'pnl_pct']]
    for idx, trade in top_trades.iterrows():
        print(f"  {trade['entry_date'].date()} → {trade['exit_date'].date()}: "
              f"${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} = "
              f"${trade['pnl']:,.2f} ({trade['pnl_pct']:+.2f}%)")

    print()
    print("📉 Top 5 pires trades:")
    print("-" * 70)
    worst_trades = trades_df.nsmallest(5, 'pnl')[['entry_date', 'exit_date', 'entry_price', 'exit_price', 'pnl', 'pnl_pct']]
    for idx, trade in worst_trades.iterrows():
        print(f"  {trade['entry_date'].date()} → {trade['exit_date'].date()}: "
              f"${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} = "
              f"${trade['pnl']:,.2f} ({trade['pnl_pct']:+.2f}%)")

    print()
    print("📊 Distribution par année:")
    print("-" * 70)

    trades_df['year'] = pd.to_datetime(trades_df['exit_date']).dt.year
    yearly = trades_df.groupby('year').agg({
        'pnl': ['count', 'sum', 'mean'],
    }).round(2)

    print(yearly.to_string())

else:
    print("❌ Aucun trade exécuté")
    print()
    print("Raisons possibles:")
    print("  - Filtre de tendance trop restrictif")
    print("  - Pas assez de données pour calculer SMA(200)")
    print("  - Taille de brique inadaptée")
    print()
    print("Solutions:")
    print("  - Réduire trend_sma_period à 50 ou 100")
    print("  - Désactiver use_trend_filter")
    print("  - Ajuster brick_size")

print()
print("=" * 70)

# Statistiques finales
metrics = backtest.metrics.get_all_metrics()
bh_return = ((price_data['close'].iloc[-1] / price_data['close'].iloc[0]) - 1) * 100

print("📈 COMPARAISON FINALE")
print("=" * 70)
print(f"Stratégie Renko:        {metrics['total_return_pct']:+.2f}%")
print(f"Buy & Hold:             {bh_return:+.2f}%")
print(f"Différence:             {metrics['total_return_pct'] - bh_return:+.2f}%")
print()
print(f"Capital initial:        ${config.initial_capital:,.2f}")
print(f"Capital final:          ${metrics['final_equity']:,.2f}")
print(f"Profit net:             ${metrics['total_return_dollars']:,.2f}")
print()
print(f"Sharpe Ratio:           {metrics['sharpe_ratio']:.2f}")
print(f"Calmar Ratio:           {metrics['calmar_ratio']:.2f}")
print(f"Max Drawdown:           {metrics['max_drawdown_pct']:.2f}%")
print()

# Évaluation
print("🎯 ÉVALUATION")
print("=" * 70)

score = 0
feedback = []

if metrics['sharpe_ratio'] > 0.8:
    score += 1
    feedback.append("✅ Bon Sharpe Ratio (>0.8)")
else:
    feedback.append("⚠️  Sharpe Ratio faible (<0.8)")

if abs(metrics['max_drawdown_pct']) < 25:
    score += 1
    feedback.append("✅ Drawdown acceptable (<25%)")
else:
    feedback.append("⚠️  Drawdown élevé (>25%)")

if metrics['profit_factor'] > 1.5:
    score += 1
    feedback.append("✅ Bon Profit Factor (>1.5)")
else:
    feedback.append("⚠️  Profit Factor faible (<1.5)")

if metrics['win_rate'] > 40 and metrics['win_rate'] < 60:
    score += 1
    feedback.append(f"✅ Win Rate équilibré ({metrics['win_rate']:.1f}%)")
else:
    feedback.append(f"⚠️  Win Rate inhabituel ({metrics['win_rate']:.1f}%)")

if metrics['total_trades'] > 10:
    score += 1
    feedback.append(f"✅ Nombre de trades suffisant ({metrics['total_trades']})")
else:
    feedback.append(f"⚠️  Peu de trades ({metrics['total_trades']})")

for f in feedback:
    print(f)

print()
print(f"Score: {score}/5")
print()

if score >= 4:
    print("🌟 Excellent ! Stratégie performante.")
elif score >= 3:
    print("👍 Bon résultat. Quelques ajustements possibles.")
elif score >= 2:
    print("⚠️  Résultat moyen. Optimisation recommandée.")
else:
    print("❌ Résultat faible. Révision des paramètres nécessaire.")

print()
print("=" * 70)
print("BACKTEST TERMINÉ")
print("=" * 70)
print()
print("📁 Prochaines étapes:")
print("  1. Analyser les trades individuels")
print("  2. Tester différentes tailles de briques (0.008, 0.012, 0.015)")
print("  3. Optimiser la période SMA (150, 200, 250)")
print("  4. Essayer SECOND_GREEN pour confirmation")
print("  5. Tester avec allow_short=True pour bear markets")
print()
