# Renko Trend Following Strategy

## Vue d'ensemble

Stratégie de trading trend-following basée sur les briques Renko avec filtres adaptatifs, trailing stops dynamiques et gestion complète du risque.

**Version:** 1.0
**Plateformes:** MultiCharts (EasyLanguage) + Python
**Type:** Trend Following
**Direction:** Long/Short (configurable)

## 🚀 Deux implémentations disponibles

### 1️⃣ MultiCharts (EasyLanguage)
- Fichier: `RenkoTrendFollowing_Strategy.txt`
- Documentation: Ce README
- Pour traders utilisant MultiCharts
- Exécution native sur plateforme de trading

### 2️⃣ Python (Complet)
- Dossier: `python/`
- Documentation: `python/README.md`
- Pour backtesting, recherche, optimisation
- Standalone, flexible, open-source

**👉 Pour démarrer avec Python:** Voir `python/QUICKSTART.md`
**👉 Pour MultiCharts:** Continuer ce README ci-dessous

## Caractéristiques principales

- ✅ **Entrées basées sur Renko** - Capture les changements de tendance via briques Renko
- ✅ **Filtre de tendance SMA** - Évite les faux signaux contre-tendance
- ✅ **Trailing stop dynamique** - Protection automatique des profits
- ✅ **Position sizing adaptatif** - Gestion du risque basée sur l'équité
- ✅ **Multi-timeframe** - Combine Renko et barres standards
- ✅ **Paramètres optimisables** - Configuration complète pour backtesting

## Installation

### Prérequis

- **MultiCharts** version 11.0 ou supérieure
- **FlexRenko** (recommandé pour Renko percentage-based)
- Données historiques de qualité (tick data recommandé)

### Étapes d'installation

1. **Ouvrir MultiCharts PowerLanguage Editor**
   - Menu: `File > New > Strategy`

2. **Copier le code**
   - Ouvrir `RenkoTrendFollowing_Strategy.txt`
   - Copier tout le contenu
   - Coller dans le nouvel éditeur de stratégie

3. **Vérifier la syntaxe**
   - Menu: `Format > Verify`
   - Corriger toute erreur éventuelle

4. **Compiler**
   - Cliquer sur l'icône de compilation
   - La stratégie devrait apparaître dans la liste des stratégies disponibles

### Configuration des données

#### Data1 - Graphique Renko

**Option 1: FlexRenko (Recommandé)**
```
Type: FlexRenko
Size Type: Percentage
Size: 1.0% (ajustable)
Reversal: 1
Based on: Close
```

**Option 2: Renko Standard**
```
Type: Renko
Box Size: calculé selon l'instrument
(ex: 50 points pour futures, $1 pour actions)
```

#### Data2 - Barres standards

```
Type: Daily (ou votre timeframe de référence)
Session: Same as chart
Purpose: Calcul SMA pour filtre de tendance
```

**Configuration MultiCharts:**
1. Chart Data1: Renko
2. Format > Symbol > Add Data2 > Daily bars
3. Vérifier que Data2 est synchronisé avec Data1

## Paramètres

### Configuration Renko

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `RenkoType` | String | "PERCENTAGE" | Type de brique: FIXED_POINTS, PERCENTAGE, ATR_BASED |
| `RenkoSize` | Float | 0.01 | Taille (1% pour PERCENTAGE) |
| `ATRPeriod` | Int | 14 | Période ATR si mode ATR_BASED |

### Filtre de tendance

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `UseTrendFilter` | Bool | true | Active le filtre SMA |
| `TrendSMAPeriod` | Int | 200 | Période SMA (calculée sur Data2) |
| `TrendMargin` | Float | 0.00 | Marge au-dessus/en-dessous SMA (0.02 = 2%) |

### Conditions d'entrée

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `EntryConfirmType` | String | "FIRST_GREEN" | FIRST_GREEN ou SECOND_GREEN |
| `RequireNoWick` | Bool | false | Exige pas de mèche sur brique d'entrée |
| `RequirePriorRed` | Bool | true | Exige brique précédente de couleur opposée |

### Direction de trading

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `AllowLong` | Bool | true | Active positions longues |
| `AllowShort` | Bool | false | Active positions courtes |
| `ShortTrendFilter` | Bool | true | Shorts uniquement sous SMA |

### Position sizing

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `PositionSizeType` | String | "PERCENT_EQUITY" | FIXED ou PERCENT_EQUITY |
| `PositionSizeValue` | Float | 0.90 | 90% de l'équité ou nombre de contrats |
| `InitialCapital` | Float | 30000 | Capital initial pour backtest |

### Gestion du stop

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `StopType` | String | "PREVIOUS_BRICK" | Type de stop |
| `StopIntraday` | Bool | true | Vérification stop en temps réel |
| `StopTrail` | Bool | true | Trailing stop automatique |
| `ExitOnReverseBrick` | Bool | true | Sortie sur brique inverse |

## Configuration recommandée

### Pour actions (QQQ, SPY, etc.)

```
RenkoSize: 0.01 (1%)
TrendSMAPeriod: 200
UseTrendFilter: true
AllowLong: true
AllowShort: false
PositionSizeValue: 0.90
ExitOnReverseBrick: true
StopTrail: true
```

### Pour futures volatils (NQ, ES)

```
RenkoSize: 0.015 (1.5%)
TrendSMAPeriod: 200
TrendMargin: 0.01
EntryConfirmType: "SECOND_GREEN"
AllowShort: true
ShortTrendFilter: true
```

### Pour scalping (timeframes courts)

```
RenkoSize: 0.005 (0.5%)
TrendSMAPeriod: 150
EntryConfirmType: "FIRST_GREEN"
StopIntraday: true
PositionSizeValue: 0.70
```

## Logique de trading

### Entrée LONG

Conditions (toutes doivent être remplies):

1. ✅ `AllowLong = true`
2. ✅ Pas de position ouverte
3. ✅ Nouvelle brique **VERTE** vient de se fermer
4. ✅ Si `EntryConfirmType = "SECOND_GREEN"`: deuxième brique verte consécutive
5. ✅ Si `RequireNoWick = true`: pas de mèche basse
6. ✅ Si `RequirePriorRed = true`: brique précédente était rouge
7. ✅ Si `UseTrendFilter = true`: Prix > SMA(200) × (1 + TrendMargin)

**Exécution:** Ordre MARKET à la fermeture de la brique Renko

### Entrée SHORT

Conditions (toutes doivent être remplies):

1. ✅ `AllowShort = true`
2. ✅ Pas de position ouverte
3. ✅ Nouvelle brique **ROUGE** vient de se fermer
4. ✅ Si `EntryConfirmType = "SECOND_GREEN"`: deuxième brique rouge consécutive
5. ✅ Si `RequireNoWick = true`: pas de mèche haute
6. ✅ Si `RequirePriorRed = true`: brique précédente était verte
7. ✅ Si `ShortTrendFilter = true`: Prix < SMA(200) × (1 - TrendMargin)

### Sortie LONG

Sortie déclenchée si **UNE** des conditions suivantes:

1. 🛑 `ExitOnReverseBrick = true` ET nouvelle brique **ROUGE**
2. 🛑 Stop hit: Prix touche `StopLevel`
3. 🛑 Signal SHORT (si `AllowShort = true`) → Reversal

**Trailing Stop:**
- Initial: Prix de clôture de la brique d'entrée
- Update: Monte au prix de clôture de chaque nouvelle brique verte (si `StopTrail = true`)
- Direction: Monte uniquement (jamais descend)

### Sortie SHORT

Sortie déclenchée si **UNE** des conditions suivantes:

1. 🛑 `ExitOnReverseBrick = true` ET nouvelle brique **VERTE**
2. 🛑 Stop hit: Prix touche `StopLevel`
3. 🛑 Signal LONG (si `AllowLong = true`) → Reversal

**Trailing Stop:**
- Initial: Prix de clôture de la brique d'entrée
- Update: Descend au prix de clôture de chaque nouvelle brique rouge (si `StopTrail = true`)
- Direction: Descend uniquement (jamais monte)

## Backtesting

### Configuration recommandée

**Settings MultiCharts:**
```
Commission: Selon votre broker (ex: $0.50/trade pour actions)
Slippage: 1-2 ticks
Bar Magnifier: ON (pour précision intraday)
Lookback: Maximum (pour SMA 200)
```

**Période de test:**
- Minimum: 5 ans
- Recommandé: 10-20 ans
- Walk-forward: 4 ans IS / 1 an OOS

### Métriques à surveiller

**Performance:**
- Net Profit: > 50% sur 5 ans
- CAGR: > 10%
- Profit Factor: > 1.5
- Win Rate: 40-60% (typique pour trend following)

**Risque:**
- Max Drawdown: < 25%
- Calmar Ratio: > 0.5
- Sharpe Ratio: > 0.8
- Sortino Ratio: > 1.0

**Distribution:**
- Average Win / Average Loss: > 2.0
- Consecutive Losses: < 8
- Percent Time in Market: 40-70%

## Optimisation

### Paramètres à optimiser (par priorité)

**Priorité 1** (impact majeur):
```
RenkoSize: [0.004, 0.006, 0.008, 0.01, 0.015, 0.02]
TrendSMAPeriod: [150, 200, 250]
```

**Priorité 2** (impact moyen):
```
EntryConfirmType: ["FIRST_GREEN", "SECOND_GREEN"]
TrendMargin: [0.00, 0.01, 0.02]
```

**Priorité 3** (fine-tuning):
```
RequireNoWick: [true, false]
PositionSizeValue: [0.70, 0.80, 0.90, 1.00]
```

### Méthodologie

1. **Genetic Optimizer** (MultiCharts):
   - Générations: 50-100
   - Population: 64-128
   - Fitness: Sharpe Ratio ou Custom Fitness

2. **Walk-Forward Analysis**:
   - In-Sample: 4 ans
   - Out-of-Sample: 1 an
   - Rolling: Avancer de 1 an
   - Validation: OOS Sharpe > 0.6

3. **Monte Carlo**:
   - Simulations: 1000+
   - Reshuffle: Trades order
   - Confidence: 95%

## Résolution de problèmes

### Pas de trades générés

**Causes possibles:**
- ✅ Données Renko mal configurées
- ✅ Data2 non synchronisé
- ✅ SMA période > nombre de barres disponibles
- ✅ Filtre de tendance trop restrictif

**Solutions:**
- Vérifier configuration FlexRenko
- Ajouter Data2 correctement
- Réduire TrendSMAPeriod ou augmenter historique
- Temporairement mettre `UseTrendFilter = false`

### Stops non déclenchés

**Causes possibles:**
- ✅ `StopIntraday = false` mais vérification manuelle pas faite
- ✅ Stop level mal calculé
- ✅ Bar Magnifier désactivé

**Solutions:**
- Activer `StopIntraday = true`
- Vérifier variable `StopLevel` dans output
- Activer Bar Magnifier dans Strategy Properties

### Performance faible

**Causes possibles:**
- ✅ RenkoSize inadapté à la volatilité
- ✅ Trop de whipsaws (marchés range)
- ✅ Slippage/commissions trop élevés

**Solutions:**
- Tester RenkoSize plus large (0.015-0.02)
- Activer `EntryConfirmType = "SECOND_GREEN"`
- Revoir paramètres de coûts
- Ajouter filtre de volatilité (ADX)

## Évolutions futures (v2.0+)

- [ ] Filtre ADX pour éviter les ranges
- [ ] Time-based exits (sortie après N briques sans progression)
- [ ] Pyramiding (ajout de positions)
- [ ] Multi-timeframe confirmation
- [ ] Machine Learning pour détection de régime
- [ ] Dynamic position sizing basé sur ATR
- [ ] Partial exits (sorties progressives)

## Support et contribution

### Reporting de bugs

Si vous trouvez un bug:
1. Vérifier configuration Data1/Data2
2. Tester avec paramètres par défaut
3. Vérifier version MultiCharts
4. Documenter le problème avec captures d'écran

### Améliorations

Les pull requests sont les bienvenues pour:
- Optimisations de performance
- Nouvelles fonctionnalités
- Documentation améliorée
- Tests additionnels

## Avertissements

⚠️ **IMPORTANT:**

- Cette stratégie est fournie à des fins éducatives
- Backtesting passé ne garantit pas performance future
- Toujours tester en paper trading avant live
- Utiliser une gestion de risque appropriée (< 30% du capital)
- Les marchés peuvent changer et rendre la stratégie obsolète
- Consulter un conseiller financier avant trading

## License

MIT License - Libre d'utilisation, modification et distribution

## Crédits

Basé sur la spécification technique "Renko Trend Following Strategy v1.0"

---

**Version:** 1.0
**Date:** 2025-11-07
**Auteur:** Spécification technique détaillée
**Plateforme:** MultiCharts (EasyLanguage/PowerLanguage)
