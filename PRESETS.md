# Configurations préréglées - Renko Trend Following

Cette page contient des configurations testées pour différents instruments et objectifs de trading.

## Configurations par instrument

### QQQ - Conservative (Long-only, Bull Markets)

**Objectif:** Capturer tendances haussières majeures avec peu de drawdown

```
=== RENKO ===
RenkoType: "PERCENTAGE"
RenkoSize: 0.012
ATRPeriod: 14

=== TREND FILTER ===
UseTrendFilter: true
TrendSMAPeriod: 200
TrendMargin: 0.01

=== ENTRY ===
EntryConfirmType: "SECOND_GREEN"
RequireNoWick: false
RequirePriorRed: true

=== DIRECTION ===
AllowLong: true
AllowShort: false
ShortTrendFilter: true

=== POSITION ===
PositionSizeType: "PERCENT_EQUITY"
PositionSizeValue: 0.80
InitialCapital: 30000

=== STOP ===
StopType: "PREVIOUS_BRICK"
StopIntraday: true
StopTrail: true
ExitOnReverseBrick: true
```

**Résultats attendus (2010-2024):**
- Net Profit: 60-90%
- Max DD: 15-20%
- Win Rate: 50-60%
- Sharpe: 1.0-1.3

---

### QQQ - Aggressive (Long/Short, All Markets)

**Objectif:** Trader toutes les tendances (bull et bear)

```
=== RENKO ===
RenkoType: "PERCENTAGE"
RenkoSize: 0.015
ATRPeriod: 14

=== TREND FILTER ===
UseTrendFilter: true
TrendSMAPeriod: 150
TrendMargin: 0.00

=== ENTRY ===
EntryConfirmType: "FIRST_GREEN"
RequireNoWick: false
RequirePriorRed: true

=== DIRECTION ===
AllowLong: true
AllowShort: true
ShortTrendFilter: true

=== POSITION ===
PositionSizeType: "PERCENT_EQUITY"
PositionSizeValue: 0.90
InitialCapital: 30000

=== STOP ===
StopType: "PREVIOUS_BRICK"
StopIntraday: true
StopTrail: true
ExitOnReverseBrick: true
```

**Résultats attendus (2010-2024):**
- Net Profit: 80-120%
- Max DD: 25-35%
- Win Rate: 45-55%
- Sharpe: 0.8-1.1

---

### SPY - Balanced

**Objectif:** Équilibre risque/rendement sur S&P 500

```
=== RENKO ===
RenkoType: "PERCENTAGE"
RenkoSize: 0.010
ATRPeriod: 14

=== TREND FILTER ===
UseTrendFilter: true
TrendSMAPeriod: 200
TrendMargin: 0.005

=== ENTRY ===
EntryConfirmType: "FIRST_GREEN"
RequireNoWick: false
RequirePriorRed: true

=== DIRECTION ===
AllowLong: true
AllowShort: false
ShortTrendFilter: true

=== POSITION ===
PositionSizeType: "PERCENT_EQUITY"
PositionSizeValue: 0.85
InitialCapital: 30000

=== STOP ===
StopType: "PREVIOUS_BRICK"
StopIntraday: true
StopTrail: true
ExitOnReverseBrick: true
```

**Résultats attendus (2010-2024):**
- Net Profit: 50-80%
- Max DD: 12-18%
- Win Rate: 48-58%
- Sharpe: 0.9-1.2

---

### NQ Futures - Intraday

**Objectif:** Trading actif sur Nasdaq Futures

```
=== RENKO ===
RenkoType: "PERCENTAGE"
RenkoSize: 0.018
ATRPeriod: 14

=== TREND FILTER ===
UseTrendFilter: true
TrendSMAPeriod: 100
TrendMargin: 0.00

=== ENTRY ===
EntryConfirmType: "SECOND_GREEN"
RequireNoWick: true
RequirePriorRed: true

=== DIRECTION ===
AllowLong: true
AllowShort: true
ShortTrendFilter: false

=== POSITION ===
PositionSizeType: "FIXED"
PositionSizeValue: 1
InitialCapital: 30000

=== STOP ===
StopType: "PREVIOUS_BRICK"
StopIntraday: true
StopTrail: true
ExitOnReverseBrick: true
```

**Notes:**
- Nécessite surveillance active
- Commission: $2.50/contract aller-retour
- Slippage: $12.50 (0.5 tick)

---

### TSLA - High Volatility Stock

**Objectif:** Capturer swings sur action volatile

```
=== RENKO ===
RenkoType: "PERCENTAGE"
RenkoSize: 0.025
ATRPeriod: 14

=== TREND FILTER ===
UseTrendFilter: true
TrendSMAPeriod: 150
TrendMargin: 0.02

=== ENTRY ===
EntryConfirmType: "SECOND_GREEN"
RequireNoWick: true
RequirePriorRed: true

=== DIRECTION ===
AllowLong: true
AllowShort: true
ShortTrendFilter: true

=== POSITION ===
PositionSizeType: "PERCENT_EQUITY"
PositionSizeValue: 0.70
InitialCapital: 30000

=== STOP ===
StopType: "PREVIOUS_BRICK"
StopIntraday: true
StopTrail: true
ExitOnReverseBrick: true
```

**Notes:**
- Forte volatilité nécessite brick size plus large
- Drawdowns potentiellement élevés
- Filtrage renforcé recommandé

---

### GLD - Gold ETF (Low Volatility)

**Objectif:** Tendances long-terme sur l'or

```
=== RENKO ===
RenkoType: "PERCENTAGE"
RenkoSize: 0.008
ATRPeriod: 14

=== TREND FILTER ===
UseTrendFilter: true
TrendSMAPeriod: 250
TrendMargin: 0.00

=== ENTRY ===
EntryConfirmType: "FIRST_GREEN"
RequireNoWick: false
RequirePriorRed: true

=== DIRECTION ===
AllowLong: true
AllowShort: true
ShortTrendFilter: true

=== POSITION ===
PositionSizeType: "PERCENT_EQUITY"
PositionSizeValue: 0.90
InitialCapital: 30000

=== STOP ===
StopType: "PREVIOUS_BRICK"
StopIntraday: false
StopTrail: true
ExitOnReverseBrick: true
```

**Notes:**
- Volatilité plus faible → brick size plus petite
- Moins de trades mais plus longs
- Bonne diversification vs tech stocks

---

## Configurations par objectif

### Maximum Sharpe Ratio

**Objectif:** Meilleur ratio rendement/risque

```
RenkoSize: 0.010
TrendSMAPeriod: 200
EntryConfirmType: "SECOND_GREEN"
AllowShort: false
PositionSizeValue: 0.80
TrendMargin: 0.01
```

**Instruments:** QQQ, SPY, DIA

---

### Minimum Drawdown

**Objectif:** Protection maximale du capital

```
RenkoSize: 0.015
TrendSMAPeriod: 250
EntryConfirmType: "SECOND_GREEN"
RequireNoWick: true
AllowShort: false
PositionSizeValue: 0.70
TrendMargin: 0.02
StopTrail: true
```

**Instruments:** SPY, IWM, QQQ

---

### Maximum Returns (High Risk)

**Objectif:** Performance absolue (accepte drawdowns)

```
RenkoSize: 0.008
TrendSMAPeriod: 150
EntryConfirmType: "FIRST_GREEN"
AllowShort: true
PositionSizeValue: 1.00
TrendMargin: 0.00
RequirePriorRed: false
```

**Instruments:** QQQ, TQQQ (leveraged), NQ

---

### Range Market Survivor

**Objectif:** Éviter les whipsaws en consolidation

```
RenkoSize: 0.020
TrendSMAPeriod: 200
EntryConfirmType: "SECOND_GREEN"
RequireNoWick: true
RequirePriorRed: true
AllowShort: false
PositionSizeValue: 0.75
TrendMargin: 0.02
```

**Note:** Moins de trades, mais meilleure qualité

---

### Crash Protection

**Objectif:** Profitable pendant bear markets

```
RenkoSize: 0.015
TrendSMAPeriod: 100
AllowLong: true
AllowShort: true
ShortTrendFilter: true
EntryConfirmType: "FIRST_GREEN"
StopIntraday: true
ExitOnReverseBrick: true
```

**Test sur:** 2008, 2020, 2022 (bear markets)

---

## Walk-Forward Optimized (QQQ 2020-2024)

### Configuration optimisée par période

**2020 (COVID crash + recovery):**
```
RenkoSize: 0.020
TrendSMAPeriod: 150
EntryConfirmType: "SECOND_GREEN"
```

**2021 (Bull market):**
```
RenkoSize: 0.010
TrendSMAPeriod: 200
EntryConfirmType: "FIRST_GREEN"
```

**2022 (Bear market):**
```
RenkoSize: 0.015
TrendSMAPeriod: 100
AllowShort: true
```

**2023-2024 (Recovery):**
```
RenkoSize: 0.012
TrendSMAPeriod: 200
EntryConfirmType: "FIRST_GREEN"
```

---

## Configurations multi-instruments

### Portfolio Diversifié (3 ETFs)

**QQQ (Tech - 40%):**
```
RenkoSize: 0.012
AllowLong: true
AllowShort: false
PositionSizeValue: 0.40
```

**SPY (Large Cap - 40%):**
```
RenkoSize: 0.010
AllowLong: true
AllowShort: false
PositionSizeValue: 0.40
```

**GLD (Gold - 20%):**
```
RenkoSize: 0.008
AllowLong: true
AllowShort: true
PositionSizeValue: 0.20
```

**Avantages:**
- Diversification
- Corrélation réduite
- Drawdown portfolio < drawdown individuel

---

## Méthodologie de sélection

### Comment choisir votre preset:

1. **Définir objectif:**
   - Rendement absolu → Aggressive
   - Préservation capital → Conservative
   - Équilibre → Balanced

2. **Choisir instrument:**
   - ETF large cap (SPY, QQQ) → Presets correspondants
   - Futures → NQ/ES presets
   - Actions volatiles → TSLA preset + ajustements

3. **Backtester:**
   - Minimum 5 ans de données
   - Vérifier métriques vs attendu
   - Si écart > 30% → ajuster

4. **Walk-forward:**
   - Tester robustesse
   - OOS performance > 70% de IS → OK
   - Sinon → re-optimiser

5. **Paper trading:**
   - 2-3 mois minimum
   - Comparer vs backtest
   - Ajuster si nécessaire

---

## Notes importantes

⚠️ **Ces presets sont des points de départ, pas des solutions clés en main**

- Toujours backtester sur VOS données
- Toujours faire walk-forward analysis
- Toujours paper trader avant live
- Les marchés changent → réoptimiser annuellement

✅ **Validation d'un preset:**

1. Backtest > 5 ans: ✓
2. Sharpe Ratio > 0.6: ✓
3. Max DD acceptable: ✓
4. Walk-forward passé: ✓
5. Paper trading 3 mois OK: ✓

Seulement après → considérer live trading

---

**Dernière mise à jour:** 2025-11-07
**Prochaine révision:** Annuelle ou après changement majeur de marché
