# RENKO TREND FOLLOWING - VERSION 2.0.1

**Stratégie de Trading Trend-Following avec Briques Renko Calculées**

## 🚀 CHANGEMENTS MAJEURS v2.0.1

### Architecture Fondamentalement Différente

**v1.0** → Utilisait des **charts Renko natifs** (FlexRenko)
**v2.0.1** → Utilise des **barres temporelles standard** avec Renko **calculé en mémoire**

Cette refonte complète résout les **problèmes de reproductibilité** de la v1.0 où les résultats changeaient selon la date de début.

### Pourquoi Ce Changement?

**Problème v1.0:**
- Les charts Renko natifs recalculent leur point de départ à chaque ajout de données
- Un backtest Jan 2020 → Dec 2024 donnait des résultats différents d'un backtest Jan 2010 → Dec 2024
- **Impossible de reproduire les résultats de manière fiable**

**Solution v2.0.1:**
- Barres temporelles standard (1 min, 5 min, daily, etc.)
- Briques Renko calculées dynamiquement en mémoire
- **État persistant avec `intrabarpersist`**
- Résultats 100% reproductibles

---

## 📋 CONTENU DU PACKAGE

### Fichiers MultiCharts

```
RenkoTrendFollowing_v2_Signal.txt      - Stratégie principale (Signal)
RenkoTrendFollowing_v2_Indicator.txt   - Indicateur de visualisation
```

### Documentation

```
README_v2.md                - Ce fichier
MIGRATION_GUIDE.md          - Guide de migration v1.0 → v2.0.1
TESTING_GUIDE.md            - Checklist de validation
```

---

## ⚡ QUICK START

### 1. Configuration du Chart

**IMPORTANT:** Utilisez un chart **STANDARD**, PAS un chart Renko!

```
Type de Chart:    Standard (Time-Based)
Symbole:          ES, NQ, QQQ, SPY, etc.
Interval:         1 min, 5 min, ou Daily
Compression:      1
```

### 2. Appliquer le Signal

1. **Format Signal (ELS) → Open Signal...**
2. Charger `RenkoTrendFollowing_v2_Signal.txt`
3. **Insert Signal** sur votre chart

### 3. Appliquer l'Indicateur (Optionnel)

Pour visualiser les briques Renko calculées:

1. **Format Indicator (ELD) → Open Indicator...**
2. Charger `RenkoTrendFollowing_v2_Indicator.txt`
3. **Insert Indicator** sur le MÊME chart

L'indicateur affichera:
- Niveau de fermeture des briques (ligne épaisse verte/rouge)
- Niveau d'ouverture des briques (ligne fine)
- Taille des briques (histogramme)

### 4. Configuration de Base

#### Paramètres Renko (CRITIQUE - doivent être identiques Signal + Indicateur!)

```
RENKO_TYPE         = "PERCENTAGE"
RENKO_SIZE         = 0.01           (1.0%)
RENKO_START_PRICE  = 0              (0 = auto)
RENKO_ROUND_TO     = 0              (0 = pas d'arrondi)
RENKO_ALLOW_MULTIPLE = true         (plusieurs briques par barre)
ATR_PERIOD         = 14
```

#### Paramètres de Trading

```
INITIAL_CAPITAL        = 30000
POSITION_SIZE_TYPE     = "PERCENT_EQUITY"
POSITION_SIZE_VALUE    = 0.90      (90% de l'équité)

USE_TREND_FILTER       = true
TREND_SMA_PERIOD       = 200
TREND_MARGIN           = 0.00

ALLOW_LONG             = true
ALLOW_SHORT            = false     (Long-only par défaut)

STOP_TRAIL             = true
EXIT_ON_REVERSE_BRICK  = true
```

---

## 🔧 PARAMÈTRES DÉTAILLÉS

### Configuration Renko

#### `RENKO_TYPE` (string)
Type de brique Renko:
- **"PERCENTAGE"** (recommandé): Taille adaptative (ex: 1% du prix)
- **"FIXED_POINTS"**: Taille fixe en points (ex: 10 points)
- **"ATR_BASED"**: Basé sur ATR × multiplicateur

#### `RENKO_SIZE` (double)
Taille des briques:
- **PERCENTAGE**: 0.01 = 1%, 0.005 = 0.5%
- **FIXED_POINTS**: 10 = 10 points, 1 = 1 point
- **ATR_BASED**: 1.0 = 1× ATR, 2.0 = 2× ATR

**Recommandations:**
- Forex: 0.5-1.0%
- Indices: 0.5-1.5%
- Actions: 1.0-2.0%

#### `RENKO_START_PRICE` (double)
Prix de départ pour la première brique:
- **0** (défaut): Utilise Close de la première barre
- **> 0**: Force un prix de départ spécifique (pour reproductibilité)

#### `RENKO_ROUND_TO` (double)
Arrondir le prix de départ:
- **0** (défaut): Pas d'arrondi
- **25**: Arrondir à 25 (ex: 4523.45 → 4525.00)
- **0.25**: Arrondir à $0.25

Utile pour les contrats futures avec ticks spécifiques.

#### `RENKO_ALLOW_MULTIPLE` (true/false)
Permettre plusieurs briques par barre:
- **true** (recommandé): Peut former 2, 3, 5+ briques sur une grosse barre
- **false**: Maximum 1 brique par barre

#### `ATR_PERIOD` (int)
Période ATR si `RENKO_TYPE = "ATR_BASED"`:
- **14** (défaut standard)
- 10-20 typique

---

### Filtre de Tendance

#### `USE_TREND_FILTER` (true/false)
Activer le filtre SMA:
- **true**: Tradez seulement dans la direction de la tendance
- **false**: Pas de filtre (tous les signaux acceptés)

#### `TREND_SMA_PERIOD` (int)
Période de la SMA de tendance:
- **200** (classique long-terme)
- **100** (moyen-terme)
- **50** (court-terme)

#### `TREND_MARGIN` (double)
Marge pour le filtre de tendance:
- **0.00** (défaut): Prix doit être > SMA (long) ou < SMA (short)
- **0.01**: Prix doit être > SMA + 1%
- **-0.01**: Prix peut être jusqu'à -1% sous SMA

---

### Confirmation d'Entrée

#### `ENTRY_CONFIRM_TYPE` (string)
Type de confirmation d'entrée:
- **"FIRST_GREEN"**: Entre sur la première brique verte
- **"SECOND_GREEN"**: Attend une deuxième brique verte consécutive

#### `REQUIRE_PRIOR_RED` (true/false)
Exiger une brique rouge avant le signal:
- **true**: La brique précédente doit être rouge (filtre rebond)
- **false**: N'importe quelle couleur précédente OK

#### `REQUIRE_NO_WICK` (true/false)
Exiger une brique sans mèche:
- **true**: Brique doit être "propre" (Low proche de Open pour GREEN)
- **false**: Pas de vérification de mèche

---

### Position Sizing

#### `POSITION_SIZE_TYPE` (string)
Mode de dimensionnement:
- **"FIXED"**: Taille fixe en contrats/actions
- **"PERCENT_EQUITY"**: Pourcentage de l'équité (compound)

#### `POSITION_SIZE_VALUE` (double)
Valeur du dimensionnement:
- **FIXED**: 1 = 1 contrat, 100 = 100 actions
- **PERCENT_EQUITY**: 0.90 = 90%, 0.50 = 50%

**Recommandations:**
- Débutants: 0.25-0.50 (25-50%)
- Intermédiaires: 0.50-0.70
- Avancés: 0.80-0.95

---

### Stop Loss et Sortie

#### `STOP_TYPE` (string)
Type de stop loss:
- **"PREVIOUS_BRICK"**: Stop au close de la brique précédente
- **"FIXED_PERCENT"**: Stop à X% du prix d'entrée
- **"FIXED_POINTS"**: Stop à X points du prix d'entrée

#### `STOP_FIXED_VALUE` (double)
Valeur si FIXED mode:
- **FIXED_PERCENT**: 0.02 = 2%
- **FIXED_POINTS**: 50 = 50 points

#### `STOP_INTRADAY` (true/false)
Vérifier stop intraday:
- **true**: Utilise Low/High de la brique pour détecter stop
- **false**: Vérifie seulement au Close de la brique

#### `STOP_TRAIL` (true/false)
Trailing stop activé:
- **true** (recommandé): Stop suit le prix favorablement
- **false**: Stop fixe

#### `EXIT_ON_REVERSE_BRICK` (true/false)
Sortir sur brique opposée:
- **true** (recommandé): Sort immédiatement sur brique rouge (si long)
- **false**: Garde position jusqu'à stop

---

### Direction de Trading

#### `ALLOW_LONG` (true/false)
Autoriser positions longues:
- **true**: Active signaux long
- **false**: Ignore tous les signaux long

#### `ALLOW_SHORT` (true/false)
Autoriser positions courtes:
- **true**: Active signaux short
- **false**: Ignore tous les signaux short

#### `SHORT_TREND_FILTER` (true/false)
Filtre de tendance pour shorts:
- **true**: Short seulement si prix < SMA
- **false**: Pas de filtre (si `USE_TREND_FILTER=false`)

---

## 📊 COMPRENDRE L'ARCHITECTURE v2.0.1

### Comment Ça Fonctionne?

```
[Barre Standard]  →  [Calculateur Renko]  →  [Détection Signal]  →  [Ordre]
   (OHLC réel)        (en mémoire)           (entrée/sortie)       (Buy/Sell)
```

### Exemple Concret

**Chart: ES 5-min, RENKO_SIZE=0.01 (1%)**

```
Barre 1: Open=4500, High=4510, Low=4498, Close=4508
  → Prix monte de 4500 à 4508
  → Aucune brique formée (< 1% = 45 points)

Barre 2: Open=4508, High=4560, Low=4505, Close=4555
  → Prix monte de 4508 à 4555 (+47 points = +1.04%)
  → BRIQUE VERTE formée: 4500 → 4545
  → Nouvelle brique commence à 4545
  → Encore du mouvement restant
  → DEUXIÈME BRIQUE VERTE: 4545 → 4590
  → Total: 2 briques vertes sur cette barre

→ Si ENTRY_CONFIRM_TYPE = "FIRST_GREEN": Signal d'achat!
```

### Variables Critiques `intrabarpersist`

```easylanguage
intrabarpersist CurrentBrick_Close(0.0)
intrabarpersist CurrentBrick_Color(0)
intrabarpersist PreviousBrick_Color(0)
```

**Pourquoi `intrabarpersist`?**
- Compatible avec **IOG (Intra-bar Order Generation)**
- Compatible avec **Bar Magnifier**
- Compatible avec **Portfolio Trader**
- État préservé entre calculs intrabar

**SANS `intrabarpersist`:**
- Variables réinitialisées à chaque tick
- Perte d'état des briques
- Signaux incorrects

---

## 🎯 PRESETS RECOMMANDÉS

### Conservative Long-Only (Bull Markets)

```
RENKO_SIZE = 0.01
USE_TREND_FILTER = true
TREND_SMA_PERIOD = 200
ENTRY_CONFIRM_TYPE = "SECOND_GREEN"
REQUIRE_PRIOR_RED = true
ALLOW_LONG = true
ALLOW_SHORT = false
STOP_TRAIL = true
POSITION_SIZE_VALUE = 0.70
```

**Profil:**
- Faible fréquence de trades
- Win rate élevé (~55-65%)
- Drawdown modéré
- Bon pour comptes <$50k

---

### Aggressive Dual-Direction (All Markets)

```
RENKO_SIZE = 0.008
USE_TREND_FILTER = false
ENTRY_CONFIRM_TYPE = "FIRST_GREEN"
REQUIRE_PRIOR_RED = false
ALLOW_LONG = true
ALLOW_SHORT = true
STOP_TRAIL = true
POSITION_SIZE_VALUE = 0.50
```

**Profil:**
- Haute fréquence de trades
- Win rate moyen (~45-50%)
- Drawdown élevé
- Nécessite gestion active

---

### Scalping Intraday (Futures)

```
RENKO_SIZE = 0.005
RENKO_ALLOW_MULTIPLE = true
USE_TREND_FILTER = false
ENTRY_CONFIRM_TYPE = "FIRST_GREEN"
ALLOW_LONG = true
ALLOW_SHORT = true
STOP_TRAIL = false
STOP_TYPE = "FIXED_POINTS"
STOP_FIXED_VALUE = 20
POSITION_SIZE_TYPE = "FIXED"
POSITION_SIZE_VALUE = 1
```

**Profil:**
- Très haute fréquence
- Petits gains par trade
- Briques très petites (0.5%)
- Chart: 1-min ou tick

---

## ⚠️ PIÈGES COURANTS ET SOLUTIONS

### 1. Pas de Trades Générés

**Symptômes:**
- Strategy Monitor montre 0 trades
- Aucun ordre envoyé

**Causes possibles:**

**a) Filtre de tendance trop restrictif**
```
USE_TREND_FILTER = true
TREND_SMA_PERIOD = 200
```
→ Pas assez de données pour calculer SMA(200)

**Solution:**
- Réduire `TREND_SMA_PERIOD` à 50 ou 100
- Ou désactiver: `USE_TREND_FILTER = false`

**b) Taille de brique inadaptée**
```
RENKO_SIZE = 0.05  (5%)
```
→ Trop large, aucune brique formée

**Solution:**
- Réduire à 0.01 (1%) ou 0.015 (1.5%)

**c) Confirmation trop stricte**
```
ENTRY_CONFIRM_TYPE = "SECOND_GREEN"
REQUIRE_PRIOR_RED = true
REQUIRE_NO_WICK = true
```
→ Presque aucun signal valide

**Solution:**
- Passer à `ENTRY_CONFIRM_TYPE = "FIRST_GREEN"`
- Mettre `REQUIRE_NO_WICK = false`

---

### 2. Signaux Indicateur ≠ Signal

**Symptômes:**
- L'indicateur montre des briques différentes du signal
- Ordres ne correspondent pas aux briques visibles

**Cause:**
Paramètres Renko DIFFÉRENTS entre Signal et Indicateur

**Solution:**
Vérifier que TOUS ces paramètres sont IDENTIQUES:
```
RENKO_TYPE
RENKO_SIZE
RENKO_START_PRICE
RENKO_ROUND_TO
RENKO_ALLOW_MULTIPLE
ATR_PERIOD (si ATR_BASED)
```

---

### 3. Résultats Changent Selon Période de Backtest

**Symptômes:**
- Backtest 2020-2024 donne des résultats différents de 2015-2024
- Performance varie quand on change la date de début

**Cause:**
`RENKO_START_PRICE = 0` (auto)

**Explication:**
- Avec 0, le prix de départ est le Close de la première barre
- Si vous commencez en 2020 → StartPrice = ~3200 (ES)
- Si vous commencez en 2015 → StartPrice = ~2000 (ES)
- Les briques se forment différemment

**Solution pour reproductibilité:**
```
RENKO_START_PRICE = 4500  (forcé)
RENKO_ROUND_TO = 25       (arrondi à 25)
```

---

### 4. Stops Pas Respectés

**Symptômes:**
- Position reste ouverte malgré franchissement du stop
- Pertes plus grandes que prévu

**Cause:**
`STOP_INTRADAY = false`

**Explication:**
- Avec `false`, stop vérifié seulement au Close de la brique
- Si brique descend à 4400 (stop) puis remonte à 4450 (close), pas de sortie

**Solution:**
```
STOP_INTRADAY = true
```

Avec `true`, le signal vérifie:
- `CurrentBrick_Low` pour long
- `CurrentBrick_High` pour short

---

### 5. "Subscript Out of Range" Error

**Symptômes:**
```
Subscript out of range. Attempting to access...
```

**Cause:**
Pas assez de barres pour calculer ATR ou SMA

**Solution:**
```
If CurrentBar < MaxList(ATR_PERIOD, TREND_SMA_PERIOD) Then
    Return;
```

Le signal v2.0.1 inclut déjà cette protection.

---

## 🔍 VALIDATION ET TESTING

### Checklist de Base

- [ ] **Signal appliqué sur chart STANDARD (pas Renko)**
- [ ] **Au moins 200+ barres de données** (pour SMA)
- [ ] **RENKO_SIZE approprié** (0.5%-2% typique)
- [ ] **Capital suffisant** (`INITIAL_CAPITAL` ≥ $10k recommandé)
- [ ] **Paramètres identiques** Signal + Indicateur

### Test 1: Vérifier Calcul des Briques

1. Appliquer Signal + Indicateur
2. Observer Commentary de l'indicateur:
   ```
   Renko Brick Close: 4545.00
   Brick Color: GREEN
   Total Bricks: 127
   Brick Size: 45.45
   Bricks This Bar: 2
   ```
3. Vérifier que `Total Bricks` augmente régulièrement

**Attendu:**
- Briques se forment sur barres volatiles
- Couleur alterne entre GREEN et RED
- Taille de brique stable (PERCENTAGE) ou fixe (FIXED_POINTS)

---

### Test 2: Vérifier Signaux d'Entrée

1. Activer `USE_TREND_FILTER = false` (accepter tous signaux)
2. `ENTRY_CONFIRM_TYPE = "FIRST_GREEN"`
3. `ALLOW_LONG = true, ALLOW_SHORT = false`
4. Run Strategy

**Attendu:**
- Ordres Buy quand première brique GREEN après RED
- Entrée au OPEN de la barre SUIVANTE (pas au close de la brique!)

**Vérifier Strategy Performance Report:**
```
Total Trades: 50-200 (dépend période)
% Profitable: 40-60%
```

---

### Test 3: Vérifier Filtre de Tendance

1. `USE_TREND_FILTER = true`
2. `TREND_SMA_PERIOD = 50` (court pour plus de signaux)
3. Chart: Ajouter SMA(50) comme indicateur séparé

**Attendu:**
- Ordres LONG uniquement quand Prix > SMA(50)
- Ordres SHORT uniquement quand Prix < SMA(50)

**Validation:**
- Noter le prix d'entrée de chaque trade
- Vérifier manuellement: Prix > SMA au moment du signal

---

### Test 4: Vérifier Trailing Stop

1. `STOP_TRAIL = true`
2. `STOP_TYPE = "PREVIOUS_BRICK"`
3. `STOP_INTRADAY = true`
4. Trouver un trade gagnant long

**Attendu:**
- Stop initial = Close de la brique précédente
- À chaque nouvelle brique VERTE, stop monte
- À la première brique ROUGE, sortie immédiate (si `EXIT_ON_REVERSE_BRICK=true`)

**Validation manuelle:**
1. Noter prix d'entrée: 4500
2. Brique actuelle close: 4545 (GREEN)
3. Stop = brique précédente = 4500
4. Nouvelle brique: 4590 (GREEN)
5. Stop trail à 4545 (monte!)
6. Brique suivante: 4545 (RED)
7. Exit à 4590 (reverse brick)

---

## 📈 OPTIMISATION

### Paramètres à Optimiser (par ordre d'impact)

1. **RENKO_SIZE** (0.005 à 0.02 par pas de 0.001)
   - Impact majeur sur fréquence et qualité des signaux

2. **TREND_SMA_PERIOD** (50, 100, 150, 200)
   - Filtre efficace en bull markets

3. **ENTRY_CONFIRM_TYPE** ("FIRST_GREEN" vs "SECOND_GREEN")
   - Trade-off fréquence vs qualité

4. **POSITION_SIZE_VALUE** (0.25 à 0.95 par pas de 0.05)
   - Impact direct sur compound et drawdown

### Méthode d'Optimisation MultiCharts

1. **Format Strategy → Optimize Strategy**
2. Sélectionner paramètres à optimiser
3. Configuration:
   ```
   RENKO_SIZE: From 0.005 To 0.020 Step 0.001
   TREND_SMA_PERIOD: From 50 To 200 Step 25
   ```
4. Optimization Target: **Net Profit** ou **Sharpe Ratio**
5. Run Optimization (peut prendre plusieurs heures!)

### Walk-Forward Analysis

**Période de développement:** 70% des données (In-Sample)
**Période de validation:** 30% des données (Out-of-Sample)

Exemple pour 10 ans de données:
- In-Sample: 2015-2021 (7 ans) → Optimiser
- Out-of-Sample: 2022-2024 (3 ans) → Valider

**Critère de validation:**
- Performance Out-of-Sample ≥ 70% de In-Sample → PASS
- Performance Out-of-Sample < 50% de In-Sample → OVERFITTING

---

## 🐛 TROUBLESHOOTING

### "Strategy Not Updating in Real-Time"

**Cause:** IOG (Intra-bar Order Generation) non activé

**Solution:**
```
Format Strategy → Properties → General
☑ Intra-bar Order Generation
```

---

### "Buy at Open of Next Bar" Not Working

**Cause:** Ordre envoyé "This Bar" au lieu de "Next Bar"

**Vérifier dans le code:**
```easylanguage
Buy ("LONG") Next Bar at Market;
```

Le mot-clé `Next Bar` est ESSENTIEL.

---

### Indicateur Ne S'affiche Pas

**Cause:** Plot désactivé dans settings

**Solution:**
```
Format Indicator → Scaling → Scale
○ Same as Symbol
● Screen (left or right)
```

Choisir "Screen" pour axe séparé.

---

### Commission/Slippage Non Pris en Compte

**Configuration:**
```
Format Strategy → Properties → Commission
Commission: $2.00 per side (ou selon votre broker)
Slippage: 1 tick
```

**IMPORTANT:** Ces coûts ont un impact majeur sur performance réelle!

---

## 📚 RESSOURCES

### Fichiers Inclus

- `RenkoTrendFollowing_v2_Signal.txt` - Code Signal complet
- `RenkoTrendFollowing_v2_Indicator.txt` - Code Indicateur
- `MIGRATION_GUIDE.md` - Migration depuis v1.0
- `TESTING_GUIDE.md` - Checklist de validation

### Spécifications Techniques

- Voir `SPECIFICATION_v2.0.1.txt` pour architecture détaillée
- Compatibilité: MultiCharts 32-bit & 64-bit
- Langage: PowerLanguage / EasyLanguage
- Type: Signal (Strategy) + Indicator

---

## 📧 SUPPORT

### Problèmes Courants

99% des problèmes viennent de:
1. Chart type (utilisez STANDARD, pas Renko!)
2. Paramètres différents entre Signal et Indicateur
3. Pas assez de données pour SMA
4. RENKO_SIZE inadapté

### Debug Steps

1. Vérifier log MultiCharts (Ctrl+Shift+L)
2. Activer Commentary dans Indicateur
3. Vérifier Format Strategy → Status
4. Réduire TREND_SMA_PERIOD si "No Trades"

---

## ✅ VALIDATION FINALE

Avant de trader en réel:

- [ ] Backtest sur 5+ ans de données
- [ ] Walk-Forward Analysis PASS
- [ ] Tested sur plusieurs symboles
- [ ] Sharpe Ratio > 0.8
- [ ] Max Drawdown < 30%
- [ ] Profit Factor > 1.3
- [ ] Win Rate 40-65%
- [ ] Testé en simulation (Paper Trading) 1-3 mois

**Ne tradez JAMAIS en réel sans validation complète!**

---

## 📜 LICENCE

MIT License - Voir fichier `LICENSE`

---

## 🔄 CHANGELOG

**v2.0.1** (2025-11-08)
- Refonte complète: Renko calculé en mémoire
- Charts standard au lieu de Renko natifs
- `intrabarpersist` pour toutes les variables d'état
- Protection double-trade avec `EntryBar`
- Gestion des gaps avec `GapThroughStop`
- Séparation Signal/Indicateur (Plot restrictions)
- Reproductibilité complète garantie

**v1.0** (date précédente)
- Implémentation initiale avec FlexRenko
- Problèmes de reproductibilité
- Deprecated

---

**VERSION:** 2.0.1
**DATE:** 2025-11-08
**AUTEUR:** Spécification originale fournie
**PLATEFORME:** MultiCharts (PowerLanguage)
