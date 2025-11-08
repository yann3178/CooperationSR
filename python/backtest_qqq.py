#!/usr/bin/env python3
"""
Backtest QQQ avec données réalistes
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import pandas as pd
from backtest import Backtest, load_price_data
from strategy import StrategyConfig

print("=" * 70)
print("BACKTEST RENKO TREND FOLLOWING - NASDAQ QQQ (2010-2024)")
print("=" * 70)
print()

# Charger les données
data_file = Path('data/QQQ_realistic_2010_2024.csv')

if not data_file.exists():
    print("❌ Fichier de données non trouvé. Création...")
    import subprocess
    subprocess.run(['python', 'create_realistic_qq_data.py'])

df = load_price_data(str(data_file))

print(f"📊 Données chargées:")
print(f"   Période: {df.index[0].date()} → {df.index[-1].date()}")
print(f"   Barres: {len(df)}")
print(f"   Prix: ${df['close'].iloc[0]:.2f} → ${df['close'].iloc[-1]:.2f}")
print(f"   Buy & Hold: {((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%")
print()

# Configuration stratégie (Conservative Long-Only)
config = StrategyConfig(
    use_trend_filter=True,
    trend_sma_period=200,
    trend_margin=0.00,
    entry_confirm_type="FIRST_GREEN",
    require_no_wick=False,
    require_prior_red=True,
    allow_long=True,
    allow_short=False,
    position_size_type="PERCENT_EQUITY",
    position_size_value=0.90,
    initial_capital=30000,
    stop_trail=True,
    exit_on_reverse_brick=True
)

print("⚙️  Configuration:")
print(f"   Capital initial: ${config.initial_capital:,.2f}")
print(f"   Taille brique: 1.0% (PERCENTAGE)")
print(f"   Filtre SMA: {config.trend_sma_period}")
print(f"   Direction: LONG uniquement")
print(f"   Trailing stop: Activé")
print()

# Backtest
backtest = Backtest(df, config, "PERCENTAGE", 0.01, 14)
summary = backtest.run()

# Rapport
print()
backtest.print_report()

# Détails des trades
print("\n" + "=" * 70)
print("TOP TRADES")
print("=" * 70)

trades = backtest.trades_df
if not trades.empty:
    print("\n🏆 Meilleurs trades:")
    top5 = trades.nlargest(5, 'pnl')
    for idx, t in top5.iterrows():
        print(f"   {t['entry_date'].date()} → {t['exit_date'].date()}: "
              f"${t['entry_price']:.2f} → ${t['exit_price']:.2f} = "
              f"${t['pnl']:,.2f} ({t['pnl_pct']:+.2f}%)")

    print("\n📉 Pires trades:")
    worst5 = trades.nsmallest(5, 'pnl')
    for idx, t in worst5.iterrows():
        print(f"   {t['entry_date'].date()} → {t['exit_date'].date()}: "
              f"${t['entry_price']:.2f} → ${t['exit_price']:.2f} = "
              f"${t['pnl']:,.2f} ({t['pnl_pct']:+.2f}%)")

print("\n" + "=" * 70)
print("✅ BACKTEST TERMINÉ")
print("=" * 70)
