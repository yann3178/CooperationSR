#!/usr/bin/env python3
"""
Créer des données réalistes simulées pour QQQ

Basé sur la performance réelle de QQQ:
- 2010: ~$47
- 2024: ~$480
- Performance: ~+920% sur 15 ans
- Volatilité annuelle: ~20%
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Seed pour reproductibilité
np.random.seed(42)

# Paramètres basés sur QQQ réel
start_price = 47.0  # Prix approximatif en 2010
end_price = 480.0   # Prix approximatif fin 2024
n_years = 15
annual_vol = 0.20   # 20% volatilité annuelle

# Générer dates (jours de trading seulement)
dates = pd.date_range('2010-01-01', '2024-12-31', freq='D')
dates = dates[dates.dayofweek < 5]  # Retirer weekends

n_days = len(dates)

# Calculer le drift pour atteindre le prix final
total_return = (end_price / start_price)
annual_return = total_return ** (1/n_years) - 1
daily_return = (1 + annual_return) ** (1/252) - 1
daily_vol = annual_vol / np.sqrt(252)

# Générer les returns avec GBM (Geometric Brownian Motion)
returns = np.random.normal(daily_return, daily_vol, n_days)

# Ajouter quelques événements marquants
# COVID crash (Mars 2020)
covid_start = (pd.Timestamp('2020-02-20') - dates[0]).days
covid_end = (pd.Timestamp('2020-03-23') - dates[0]).days
if covid_start > 0 and covid_end < n_days:
    returns[covid_start:covid_end] = np.random.normal(-0.03, 0.05, covid_end - covid_start)

# Générer la série de prix
price_path = start_price * np.exp(np.cumsum(returns))

# Ajouter une légère tendance pour atteindre exactement le prix final
adjustment = (end_price / price_path[-1]) ** (1/n_days)
price_path = price_path * (adjustment ** np.arange(n_days))

# Créer OHLC data
data = []
for i, (date, close) in enumerate(zip(dates, price_path)):
    # Générer high/low autour du close
    daily_range = close * daily_vol * np.random.uniform(1.0, 2.5)

    high = close + daily_range * np.random.uniform(0.3, 0.7)
    low = close - daily_range * np.random.uniform(0.3, 0.7)
    open_price = low + (high - low) * np.random.uniform(0.2, 0.8)

    # Ensure OHLC relationships
    high = max(high, open_price, close)
    low = min(low, open_price, close)

    volume = int(np.random.lognormal(17.5, 0.3))  # ~40-100M shares

    data.append({
        'Date': date,
        'Open': round(open_price, 2),
        'High': round(high, 2),
        'Low': round(low, 2),
        'Close': round(close, 2),
        'Volume': volume
    })

df = pd.DataFrame(data)

# Sauvegarder
data_dir = Path('data')
data_dir.mkdir(exist_ok=True)

output_file = data_dir / 'QQQ_realistic_2010_2024.csv'
df.to_csv(output_file, index=False)

print("✓ Données QQQ réalistes créées")
print(f"  Fichier: {output_file}")
print(f"  Période: {df['Date'].iloc[0].date()} à {df['Date'].iloc[-1].date()}")
print(f"  Barres: {len(df)}")
print(f"  Prix: ${df['Close'].iloc[0]:.2f} → ${df['Close'].iloc[-1]:.2f}")
print(f"  Performance: {((df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1) * 100:.2f}%")
print(f"  CAGR: {((df['Close'].iloc[-1] / df['Close'].iloc[0]) ** (1/n_years) - 1) * 100:.2f}%")
print()
print("Statistiques:")
print(f"  Prix moyen: ${df['Close'].mean():.2f}")
print(f"  Prix min: ${df['Close'].min():.2f}")
print(f"  Prix max: ${df['Close'].max():.2f}")
print(f"  Volatilité (std returns): {df['Close'].pct_change().std() * np.sqrt(252) * 100:.2f}%")
