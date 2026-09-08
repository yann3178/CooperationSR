# SESSION HANDOFF — Trend-Parity Quant Research
# ================================================
#
# Ce document permet à une nouvelle instance Claude de reproduire
# l'intégralité des résultats produits dans cette session de recherche.
#
# Session originale : https://claude.ai/code/session_012xxnn6dszNMxGnvX7DFvXV
# Branche : claude/quant-strategy-backtest-fCBoE
# Dépôt : yann3178/CooperationSR

## 1. RÉSUMÉ DU PROJET

Recherche quantitative pour trouver et backtester une stratégie
d'investissement sur ETF qui bat le Nasdaq (QQQ) en PnL absolu avec
un drawdown contrôlé.

### Stratégie finale : Trend-Parity

- **Univers** : QQQ (Nasdaq-100), TLT (Treasury 20Y+), GLD (Gold), VNQ (US REITs)
- **Signal** : chaque actif est ON si Close > SMA(150), OFF sinon
- **Sizing** : inverse-volatilité (40 jours) parmi les actifs ON
- **Rebalance** : mensuel, premier jour de bourse du mois, exécution at Open
- **Coûts** : 5 bps par côté (10 bps round-trip)
- **Levier** : 1.0× (conservative) ou 1.2× (moderate)

### Résultats headline (lev 1.0×, 2005-2026)

| Métrique | Trend-Parity | QQQ Buy & Hold |
|---|---:|---:|
| CAGR | 12.5 % | 10.4 % |
| MaxDD close-to-close | −16.6 % | −83.0 % |
| Sharpe | 1.06 | 0.50 |
| Calmar | 0.76 | 0.13 |

---

## 2. ARCHITECTURE DES FICHIERS

```
quant/
├── .gitignore                    # Ignore data/, data_ohlcv/, __pycache__
│
├── ── CORE STRATEGY ──
├── framework.py                  # Backtest engine vectorisé, métriques, data loading
├── strategy.py                   # Stratégie finale + run_backtest_strategy()
├── live_signals.py               # Signaux quotidiens pour trading live
├── make_chart.py                 # Génère backtest_chart.png
├── robustness.py                 # Walk-forward, sensibilité paramètres
│
├── ── DATA ──
├── download_data.py              # Télécharge 25 ETFs daily (Close) → data/*.csv
├── data/                         # [gitignored] CSV daily closes (yfinance)
├── data_ohlcv/                   # [gitignored] CSV OHLCV (yfinance) pour ZAR/CB
│
├── ── EXPLORATION INITIALE (300+ backtests) ──
├── explore.py .. explore8.py      # Iterations 1-8 du grid search
│
├── ── KEVIN DAVEY ALGORITHM ──
├── davey_strategy.py             # Implémentation du breakout mensuel 4/5
├── davey_variants.py             # 5 variantes d'allocation + blends TP
├── davey_on_tp.py / davey_final.py
├── davey_addendum.md             # Rapport Davey
│
├── ── UNIVERSE EXPLORER (2431 combos) ──
├── backtest_universe.py          # Moteur combinatoire 3-6 actifs
├── universe_deepdive.py / universe_report.md
│
├── ── STRESS TESTS & BIAIS ──
├── stress_tests.py / stress_report.md
│
├── ── LEVERAGE ──
├── leverage_analysis.py / leverage_report.md
│
├── ── MSCI WORLD ──
├── msci_world_comparison.py
│
├── ── PEA / ÉMERGENTS ──
├── pea_emerging.py / pea_phase456.py / pea_report.md
│
├── ── DCA vs DCA+ZAR ──
├── dca_comparison.py / dca_report.md
├── dca_zar_full.py / dca_zar_full_report.md
│
├── ── CIRCUIT BREAKER + TWAP ──
├── cb_twap_engine.py / cb_twap_tests.py / decomposition.py
│
├── ── RAPPORTS & IMAGES ──
├── strategy_report.md / *.png
│
└── SESSION_HANDOFF.md / reproduce_all.sh
```

---

## 3. COMMENT REPRODUIRE TOUT DEPUIS ZÉRO

### Prérequis

```bash
pip install yfinance pandas numpy matplotlib scipy
```

### Reproduction rapide

```bash
cd quant/
bash reproduce_all.sh 2>&1 | tee reproduce_log.txt
```

Ou manuellement :

```bash
# 1. Télécharger les données
python3 download_data.py
# + OHLCV pour CB/ZAR (voir reproduce_all.sh)

# 2. Stratégie principale
python3 strategy.py
python3 robustness.py
python3 make_chart.py
python3 crisis_analysis.py

# 3. Analyses avancées
python3 backtest_universe.py
python3 stress_tests.py
python3 leverage_analysis.py
python3 dca_zar_full.py
python3 decomposition.py
```

---

## 4. SYNTHÈSE DE TOUTES LES CONCLUSIONS

### Stratégie optimale

**Trend-Parity QQQ/TLT/GLD/VNQ**, SMA-150, inverse-vol 40d, monthly rebal.
Sans levier : CAGR 12.5%, DD −16.6%, Sharpe 1.06, Calmar 0.76
Le filtre SMA fait 90% du travail alpha ; l'inverse-vol ajoute ~0.05 Sharpe

### Ce qui a été rejeté

- MaxDD ≤ 10% : infaisable (frontier limit + 2022)
- Kevin Davey breakout : −28 à −104 bps vs SMA-150
- Émergents (INDA, EEM) : Sharpe 1.06 → 0.89-0.99
- DCA+ZAR naïf : delta = $0
- DCA+ZAR Tradosaure : −28 bps/an
- Circuit breaker : 60% whipsaws, MC dégrade tail risk
- TWAP : −50 à −114 bps/an vs Open
- CB + TWAP combinés : −185 bps/an

### Ce qui a été confirmé

- VNQ améliore Sharpe +0.07, Calmar +0.18
- GLD indispensable (retirer = DD ×2, Sharpe /1.4)
- SPY plan B valide (Sharpe 0.98)
- Paramètres robustes : SMA 120-175, surface lisse
- À risque égal : TP gagne +10-15 pp CAGR vs VT/URTH
- DCA pur > toute forme de market timing
- Lev max raisonnable : 1.7-2.0×

### Implémentation live

```
PEA : Amundi PANX (QQQ), Amundi EPRA Euro (VNQ) → 50%
CTO : iShares DTLA (TLT), Invesco SGLD (GLD) → 50%
Rebalance : 1er jour ouvré, Market-on-Open
Levier : 1.0× ou 1.2×
CAGR net fiscal PEA/CTO : ~9.6% (1.0×) / ~10.6% (1.2×)
Pas de CB, TWAP, ZAR, timing intra-mois
```

---

## 5. DÉCOMPOSITION VALEUR AJOUTÉE

| Brique | ΔCAGR vs EW | ΔSharpe | ΔCalmar |
|---|---:|---:|---:|
| Rebalancement seul | −4.89 pp | +0.09 | +0.04 |
| Inverse-vol seul | +0.07 pp | +0.17 | +0.08 |
| **Filtre SMA seul** | **+2.02 pp** | +0.15 | **+0.38** |
| Combo complet | +2.05 pp | +0.20 | +0.42 |
| Synergie (diff-in-diff) | −0.04 | −0.12 | −0.04 |

Le SMA fait 99% du travail. Inv-vol et SMA sont redondants.

---

## 6. SPEC MULTICHARTS

```
Data1=QQQ  Data2=TLT  Data3=GLD  Data4=VNQ
SMA_Window=150  Vol_Window=40  Leverage=1.0 ou 1.2  CostPerSideBps=5

Logique : au 1er du mois :
- TrendOn = Close > Average(Close, 150)
- Vol = StdDev(returns, 40) × √252
- InvVol = IIf(TrendOn AND Vol > 0, 1/Vol, 0)
- Weight = Leverage × InvVol / Sum(InvVol)
- Shares = IntPortion(PortfolioEquity × Weight / Close)
- Buy/Sell shares "this bar on close"
```

---

*Session : https://claude.ai/code/session_012xxnn6dszNMxGnvX7DFvXV*
*Branche : claude/quant-strategy-backtest-fCBoE*
