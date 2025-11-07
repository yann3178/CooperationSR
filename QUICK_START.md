# Guide de démarrage rapide - Renko Trend Following

## Installation en 5 minutes

### Étape 1: Importer la stratégie dans MultiCharts

1. Ouvrir **PowerLanguage Editor**
2. Menu: `File > New > Strategy`
3. Nommer: `RenkoTrendFollowing_v1`
4. Copier/coller le contenu de `RenkoTrendFollowing_Strategy.txt`
5. Vérifier: `Format > Verify`
6. Compiler: Icône de compilation

### Étape 2: Configurer le graphique

#### Configuration Data1 (Renko)

**Méthode A: FlexRenko (Recommandé)**

1. Nouveau graphique: `File > New Chart Window`
2. Symbole: `QQQ` (ou votre instrument)
3. Type: `FlexRenko`
4. Configuration FlexRenko:
   ```
   Size Type: Percentage
   Size: 1.0
   Reversal: 1
   Bars to Build On: Close
   ```

**Méthode B: Renko Standard**

1. Nouveau graphique
2. Symbole: `QQQ`
3. Type: `Renko`
4. Box Size: Calculé automatiquement ou manuel (ex: $2 pour QQQ)

#### Configuration Data2 (Barres standards)

1. Sur le graphique Renko: `Format > Symbol > Add Data`
2. Configuration Data2:
   ```
   Symbol: Same as Data1
   Interval: Daily
   Session: Same as chart
   ```

### Étape 3: Appliquer la stratégie

1. Sur le graphique: `Format > Strategy > Add`
2. Sélectionner: `RenkoTrendFollowing_v1`
3. Paramètres recommandés pour débuter:

```
=== Configuration Renko ===
RenkoType: "PERCENTAGE"
RenkoSize: 0.01
ATRPeriod: 14

=== Filtre de tendance ===
UseTrendFilter: true
TrendSMAPeriod: 200
TrendMargin: 0.00

=== Entrée ===
EntryConfirmType: "FIRST_GREEN"
RequireNoWick: false
RequirePriorRed: true

=== Direction ===
AllowLong: true
AllowShort: false
ShortTrendFilter: true

=== Position ===
PositionSizeType: "PERCENT_EQUITY"
PositionSizeValue: 0.90
InitialCapital: 30000

=== Stop ===
StopType: "PREVIOUS_BRICK"
StopIntraday: true
StopTrail: true
ExitOnReverseBrick: true
```

4. Cliquer: `OK`

### Étape 4: Configurer le backtest

1. `Format > Strategy > Properties`
2. **Commission:**
   - Pour actions: `$1.00` par trade (aller-retour)
   - Pour futures: Selon contrat (ex: $2.50 pour NQ)
3. **Slippage:** `$0.10` (conservateur)
4. **Bar Magnifier:** `ON` (important!)
5. **Initial Capital:** `$30,000`

### Étape 5: Lancer le backtest

1. Charger données historiques: 5+ ans recommandé
2. Vérifier que Data2 a suffisamment de barres
3. Appuyer: `F3` ou bouton `Calculate`
4. Attendre calcul (peut prendre quelques minutes)

## Résultats attendus (QQQ, 2019-2024)

Avec paramètres par défaut:

- **Net Profit:** 40-80%
- **Max Drawdown:** 15-25%
- **Profit Factor:** 1.5-2.5
- **Win Rate:** 45-55%
- **Sharpe Ratio:** 0.8-1.2
- **Total Trades:** 15-30 sur 5 ans

*Note: Résultats varient selon période et instrument*

## Vérifications importantes

### ✅ Checklist avant backtest

- [ ] Data1 = Renko configuré correctement
- [ ] Data2 = Daily bars présent et synchronisé
- [ ] Strategy Properties > Bar Magnifier = ON
- [ ] Historique de données > 5 ans disponible
- [ ] Commission et slippage configurés
- [ ] TrendSMAPeriod (200) < nombre de barres disponibles

### ✅ Checklist des résultats

Après backtest, vérifier:

- [ ] Nombre de trades > 0 (si 0, voir troubleshooting)
- [ ] Strategy Performance Report généré
- [ ] Equity curve croissante sur le long terme
- [ ] Drawdown maximal acceptable (< 30%)
- [ ] Profit factor > 1.0 (minimum)

## Configurations par instrument

### QQQ (Nasdaq ETF)

```
RenkoSize: 0.01 (1%)
TrendSMAPeriod: 200
AllowLong: true
AllowShort: false
UseTrendFilter: true
```

**Période recommandée:** 2000-2024 (24 ans)

### SPY (S&P 500 ETF)

```
RenkoSize: 0.008 (0.8%)
TrendSMAPeriod: 200
AllowLong: true
AllowShort: false
```

**Période recommandée:** 2000-2024

### NQ (Nasdaq Futures)

```
RenkoSize: 0.015 (1.5%)
TrendSMAPeriod: 200
AllowLong: true
AllowShort: true
EntryConfirmType: "SECOND_GREEN"
```

**Note:** Nécessite gestion intraday, plus volatile

### ES (E-mini S&P 500)

```
RenkoSize: 0.01 (1%)
TrendSMAPeriod: 200
AllowLong: true
AllowShort: true
```

### TSLA (Action volatile)

```
RenkoSize: 0.02 (2%)
TrendSMAPeriod: 150
EntryConfirmType: "SECOND_GREEN"
RequireNoWick: true
```

**Note:** Plus de filtrage nécessaire

## Troubleshooting rapide

### Problème: Aucun trade généré

**Solution 1:** Vérifier Data2
```
Format > Symbol > vérifier Data2 présent
```

**Solution 2:** Réduire période SMA
```
TrendSMAPeriod: 200 → 100
```

**Solution 3:** Désactiver filtre temporairement
```
UseTrendFilter: true → false
```

### Problème: Trop de trades (whipsaw)

**Solution:**
```
EntryConfirmType: "FIRST_GREEN" → "SECOND_GREEN"
RenkoSize: 0.01 → 0.015 ou 0.02
```

### Problème: Pas assez de trades

**Solution:**
```
RenkoSize: 0.01 → 0.006 ou 0.008
EntryConfirmType: "SECOND_GREEN" → "FIRST_GREEN"
RequirePriorRed: true → false
```

### Problème: Drawdown trop élevé

**Solution:**
```
PositionSizeValue: 0.90 → 0.70
TrendMargin: 0.00 → 0.02
StopTrail: false → true (si déjà false)
```

### Problème: Performance Strategy Report vide

**Solution:**
```
1. Vérifier Bar Magnifier = ON
2. Recharger données: F5
3. Recalculer: F3
4. Vérifier période de test > 1 an
```

## Optimisation simple

### Test 1: Taille Renko

Tester ces valeurs de `RenkoSize`:
```
0.004, 0.006, 0.008, 0.01, 0.015, 0.02
```

**Critère:** Meilleur Sharpe Ratio

### Test 2: Période SMA

Tester ces valeurs de `TrendSMAPeriod`:
```
100, 150, 200, 250
```

**Critère:** Meilleur Calmar Ratio (Return/DD)

### Test 3: Confirmation

Tester:
```
EntryConfirmType: "FIRST_GREEN" vs "SECOND_GREEN"
```

**Critère:** Profit Factor > 1.5 ET Win Rate acceptable

## Passer au live trading

### Avant de trader en réel:

1. **Backtest validé** (5+ ans, Sharpe > 0.8)
2. **Walk-forward analysis** passé
3. **Paper trading** 2-3 mois sans erreur
4. **Broker compatible** avec MultiCharts automation
5. **Capital risqué** < 30% du capital total
6. **Surveillance** quotidienne mise en place

### Configuration live:

```
PositionSizeValue: 0.50-0.70 (plus conservateur)
StopIntraday: true (obligatoire)
Commission/Slippage: Réalistes (tester avec valeurs élevées)
```

### Monitoring:

- Vérifier positions ouvertes 1x/jour minimum
- Logger tous les trades dans fichier externe
- Comparer performance live vs backtest
- Stop immédiat si divergence > 20% après 20 trades

## Ressources supplémentaires

- **Documentation complète:** `README.md`
- **Spécification technique:** Voir fichier spec original
- **Support MultiCharts:** https://www.multicharts.com/support
- **FlexRenko Guide:** MultiCharts Help > FlexRenko

## Prochaines étapes

1. ✅ Terminer configuration initiale
2. ✅ Lancer premier backtest avec paramètres par défaut
3. ✅ Analyser résultats (Performance Report)
4. ✅ Optimiser paramètres principaux (Renko size, SMA)
5. ✅ Walk-forward analysis
6. ✅ Paper trading
7. ✅ Live trading (petit capital)

---

**Questions fréquentes:** Voir README.md section "Résolution de problèmes"
**Configuration avancée:** Voir spécification technique complète
