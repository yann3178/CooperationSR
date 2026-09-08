#!/usr/bin/env bash
# reproduce_all.sh — Reproduit TOUS les résultats de la session Trend-Parity
#
# Usage :
#   pip install yfinance pandas numpy matplotlib scipy
#   cd quant/
#   bash reproduce_all.sh 2>&1 | tee reproduce_log.txt
#
# Durée totale estimée : ~20-30 minutes
# Dépendances : Python 3.10+, pip packages ci-dessus, connexion internet (yfinance)

set -e
echo "============================================================"
echo "  TREND-PARITY — REPRODUCTION COMPLÈTE"
echo "  $(date)"
echo "============================================================"

# ── 1. Téléchargement des données ──
echo -e "\n[1/12] Téléchargement données Close daily (25 ETFs)..."
python3 download_data.py

echo -e "\n[2/12] Téléchargement données OHLCV (4 ETFs)..."
python3 -c "
import yfinance as yf; import pandas as pd; import os
os.makedirs('data_ohlcv', exist_ok=True)
for sym in ['QQQ','TLT','GLD','VNQ']:
    df = yf.download(sym, start='2004-01-01', end='2026-12-31', auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.to_csv(f'data_ohlcv/{sym}.csv')
    print(f'  {sym}: {len(df)} rows')
"

echo -e "\n[3/12] ETFs supplémentaires (émergents, MSCI World)..."
python3 -c "
import yfinance as yf; import pandas as pd
extra = ['XLF','EEM','VNQ','TIP','LQD','VT','URTH','INDA','FXI','EWZ','EWY',
         'THD','VNM','EWW','EIDO','TUR','VNQI','RWX','BWX','EMB']
for tk in extra:
    try:
        df = yf.download(tk, start='1990-01-01', end='2026-12-31', auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = [c[0] for c in df.columns]
        if not df.empty: df.to_csv(f'data/{tk}.csv'); print(f'  {tk}: OK')
    except: print(f'  {tk}: SKIP')
"

# ── 2. Stratégie principale ──
echo -e "\n[4/12] Stratégie Trend-Parity (métriques headline)..."
python3 strategy.py

echo -e "\n[5/12] Robustesse (walk-forward, sensibilité)..."
python3 robustness.py

echo -e "\n[6/12] Graphique principal..."
python3 make_chart.py

echo -e "\n[7/12] Analyse de crises (dot-com, GFC, Covid, 2022)..."
python3 crisis_analysis.py

# ── 3. Analyses avancées ──
echo -e "\n[8/12] Universe Explorer (2431 combos, ~5 min)..."
python3 backtest_universe.py

echo -e "\n[9/12] Stress tests (biais QQQ/GLD, sous-périodes, corrélation)..."
python3 stress_tests.py

echo -e "\n[10/12] Leverage analysis (1.0-3.0×, Monte Carlo)..."
python3 leverage_analysis.py

echo -e "\n[11/12] DCA vs DCA+ZAR (spec Tradosaure complète)..."
python3 dca_zar_full.py

echo -e "\n[12/12] Décomposition valeur ajoutée..."
python3 decomposition.py

echo -e "\n============================================================"
echo "  REPRODUCTION TERMINÉE — $(date)"
echo "  Vérifier les rapports dans quant/*.md et quant/*.png"
echo "============================================================"
