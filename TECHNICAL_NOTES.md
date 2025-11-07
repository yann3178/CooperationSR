# Notes techniques - Renko Trend Following Strategy

## Architecture du code

### Structure générale

```
RenkoTrendFollowing_Strategy.txt
├── Header & Documentation
├── Inputs (Parameters)
├── Variables (State tracking)
├── Initialization (Once Begin block)
├── Brick Analysis
├── Trend Filter Calculation
├── Position Sizing
├── Entry Logic (Long/Short)
├── Exit Logic (Long/Short)
└── Visualization
```

### Flux d'exécution

```
Pour chaque nouvelle brique Renko:
  1. Analyser propriétés brique (couleur, mèches)
  2. Calculer SMA sur Data2
  3. Évaluer conditions de tendance
  4. Calculer taille de position
  5. SI pas de position:
       Évaluer conditions d'entrée (Long/Short)
       Exécuter entrée si conditions remplies
  6. SI position ouverte:
       Mettre à jour trailing stop si applicable
       Évaluer conditions de sortie
       Exécuter sortie si conditions remplies
  7. Mettre à jour visualisation
```

## Gestion des données multi-timeframe

### Problématique

La stratégie nécessite:
- **Data1 (Renko):** Pour signaux d'entrée/sortie
- **Data2 (Standard):** Pour calcul SMA de tendance

### Solution MultiCharts

```easylanguage
// Vérification disponibilité Data2
If DataCompression = 14 Then Begin  // 14 = Renko
    UseData2 = true;
End;

// Calcul SMA sur Data2
If UseData2 and CurrentBar > TrendSMAPeriod Then Begin
    SMAValue = Average(Close of Data2, TrendSMAPeriod);
End
```

### Synchronisation

MultiCharts synchronise automatiquement Data1 et Data2:
- À chaque fermeture de brique Data1, la valeur Data2 la plus récente est utilisée
- Pas besoin de gestion manuelle du décalage temporel
- La fonction `Close of Data2` retourne le dernier close disponible

### Fallback

Si Data2 n'est pas disponible:
```easylanguage
// Fallback to Data1 if Data2 not available
SMAValue = Average(Close, TrendSMAPeriod);
```

**Note:** Ce fallback calcule la SMA sur les briques Renko elles-mêmes, ce qui n'est pas idéal mais permet un fonctionnement dégradé.

## Calcul de la taille de brique

### Mode PERCENTAGE (Recommandé)

```
Taille brique = Prix actuel × RenkoSize
```

**Exemple:**
- Prix: $25,000
- RenkoSize: 0.01 (1%)
- Taille brique: $250

**Avantages:**
- S'adapte automatiquement aux changements de prix long-terme
- Cohérent sur 20+ ans de données
- Évite briques trop petites sur instruments chers

**Implémentation:**

Dans MultiCharts avec FlexRenko:
```
Chart Settings > FlexRenko
Size Type: Percentage
Size: 1.0 (pour 1%)
```

### Mode FIXED_POINTS

```
Taille brique = RenkoSize (constant)
```

**Exemple:**
- RenkoSize: 100
- Taille brique: 100 points (toujours)

**Avantages:**
- Simple à comprendre
- Prévisible

**Inconvénients:**
- Inadapté aux grands changements de prix (ex: QQQ 2000 vs 2024)
- Peut générer trop/pas assez de briques selon période

### Mode ATR_BASED

```
Taille brique = ATR(ATRPeriod) × RenkoSize
```

**Exemple:**
- ATR(14): 500
- RenkoSize: 1.5
- Taille brique: 750 points

**Avantages:**
- S'adapte à la volatilité
- Plus de briques en période calme, moins en volatile

**Inconvénients:**
- Plus complexe
- Nécessite recalcul régulier de ATR
- Peut changer taille de brique en cours de trade

**Note:** Le mode ATR_BASED nécessite un calcul custom dans MultiCharts si FlexRenko ne le supporte pas nativement.

## Détection de couleur de brique

### Logique

```easylanguage
If BrickClose > BrickOpen Then
    CurrentBrickColor = "GREEN"  // Bullish
Else If BrickClose < BrickOpen Then
    CurrentBrickColor = "RED"    // Bearish
Else
    CurrentBrickColor = "NEUTRAL" // Doji (rare en Renko)
```

### Briques Renko "pures"

En théorie, les briques Renko n'ont que deux états:
- **Verte:** Close = Open + Taille brique
- **Rouge:** Close = Open - Taille brique

Donc `Close = Open` ne devrait jamais arriver. Le cas NEUTRAL est une sécurité.

### Comptage de briques consécutives

```easylanguage
If CurrentBrickColor = "GREEN" Then Begin
    ConsecutiveGreen = ConsecutiveGreen + 1;
    ConsecutiveRed = 0;
End Else If CurrentBrickColor = "RED" Then Begin
    ConsecutiveRed = ConsecutiveRed + 1;
    ConsecutiveGreen = 0;
End;
```

Utilisé pour `EntryConfirmType = "SECOND_GREEN"`.

## Gestion des mèches (wicks)

### Définition

Dans une implémentation Renko "pure", il n'y a pas de mèches:
- Brique verte: Low = Open, High = Close
- Brique rouge: High = Open, Low = Close

Cependant, certaines implémentations affichent les extrêmes intraday comme mèches.

### Détection

```easylanguage
HasLowerWick = (BrickLow < BrickOpen and CurrentBrickColor = "GREEN") or
               (BrickLow < BrickClose and CurrentBrickColor = "RED");

HasUpperWick = (BrickHigh > BrickClose and CurrentBrickColor = "GREEN") or
               (BrickHigh > BrickOpen and CurrentBrickColor = "RED");
```

### Utilisation

Si `RequireNoWick = true`:
- Brique verte avec lower wick → Rejetée
- Brique rouge avec upper wick → Rejetée

**Raison:** Une mèche indique une hésitation intraday, possiblement un signal moins fort.

**Note:** Avec FlexRenko standard, il ne devrait pas y avoir de mèches. Ce paramètre est surtout utile pour d'autres implémentations de Renko.

## Trailing stop

### Initialisation

```easylanguage
// À l'entrée Long
StopLevel = Close[1];  // Close de la brique précédente
```

### Mise à jour (Long)

```easylanguage
If StopTrail and CurrentBrickColor = "GREEN" Then Begin
    If BrickClose > EntryPrice Then Begin
        StopLevel = MaxList(StopLevel, Close[1]);
    End;
End;
```

**Logique:**
- Seulement si la brique actuelle est verte (tendance favorable)
- Seulement si on est en profit (BrickClose > EntryPrice)
- Le stop monte au close de la brique **précédente** (pas actuelle)
- Le stop ne descend jamais (MaxList)

**Exemple:**

```
Entry: $25,000
Brique N+1 (GREEN): Close $25,250 → Stop = $25,000 (brique entry)
Brique N+2 (GREEN): Close $25,500 → Stop = $25,250 (N+1 close)
Brique N+3 (GREEN): Close $25,750 → Stop = $25,500 (N+2 close)
Brique N+4 (RED):   Close $25,500 → Stop reste $25,500
Prix touche $25,500 → Sortie
```

### Mise à jour (Short)

```easylanguage
If StopTrail and CurrentBrickColor = "RED" Then Begin
    If BrickClose < EntryPrice Then Begin
        StopLevel = MinList(StopLevel, Close[1]);
    End;
End;
```

**Logique:** Inverse du long
- Stop descend avec chaque nouvelle brique rouge
- Stop ne monte jamais (MinList)

## Position sizing

### Mode PERCENT_EQUITY

```easylanguage
EquityValue = NetProfit + InitialCapital;
SharesToTrade = IntPortion((EquityValue * PositionSizeValue) / BrickClose);
If SharesToTrade < 1 Then SharesToTrade = 1;
```

**Exemple:**
- InitialCapital: $30,000
- NetProfit: $5,000
- EquityValue: $35,000
- PositionSizeValue: 0.90 (90%)
- BrickClose: $350
- SharesToTrade: IntPortion($31,500 / $350) = 90 shares

**Avantages:**
- Effet compound: gains réinvestis automatiquement
- Risque proportionnel au capital

**Inconvénients:**
- Drawdowns en % peuvent masquer drawdowns en $
- Nécessite surveillance du capital réel

### Mode FIXED

```easylanguage
SharesToTrade = PositionSizeValue;  // Fixed shares
```

**Exemple:**
- PositionSizeValue: 100
- SharesToTrade: 100 (toujours)

**Avantages:**
- Simple
- Prévisible

**Inconvénients:**
- Pas d'effet compound
- Risque fixe en $ mais variable en %

## Gestion des sorties

### Exit on reverse brick

```easylanguage
If ExitOnReverseBrick and CurrentBrickColor = "RED" Then Begin
    Sell("Reverse Brick Exit") next bar at market;
End;
```

**Timing:**
- Détecté: Fermeture de la première brique rouge
- Exécuté: Ouverture de la brique suivante (next bar at market)
- Slippage: Possible entre close brique rouge et open suivante

**Raison:** Sortie rapide avant que la tendance ne se retourne complètement.

### Stop loss

**Mode Intraday:**
```easylanguage
Sell("Stop Loss") next bar at StopLevel stop;
```

- MultiCharts surveille le prix en temps réel
- Sortie dès que prix touche StopLevel
- Exécution peut être intraday (avant fermeture brique)

**Mode End-of-Day:**
```easylanguage
If BrickClose <= StopLevel Then Begin
    Sell("Stop Loss EOD") next bar at market;
End;
```

- Vérification uniquement à la fermeture de chaque brique
- Peut laisser passer des drawdowns intraday

**Recommandation:** `StopIntraday = true` pour protection maximale.

### Reversal

```easylanguage
// Si en Long et signal Short
If AllowShort and CanEnterShort Then Begin
    Sell("Reversal Exit") next bar at market;
End;
```

Ferme le Long immédiatement, puis le code Short ouvre la position Short.

## Optimisation du code

### Variables globales vs locales

Toutes les variables sont déclarées en section `Variables` (globales au script).

**Raison:** EasyLanguage ne supporte pas de variables locales dans les blocs.

### Calculs répétés

Certains calculs sont répétés (ex: `Close[1]` appelé plusieurs fois).

**Optimisation possible:**
```easylanguage
Vars: PreviousClose(0);
PreviousClose = Close[1];
// Utiliser PreviousClose au lieu de Close[1] partout
```

**Impact:** Minime sur Renko (peu de barres), mais utile pour optimisation.

### Conditions complexes

Les conditions d'entrée sont évaluées séquentiellement:

```easylanguage
CanEnterLong = true;
If ... Then CanEnterLong = false;
If ... Then CanEnterLong = false;
...
```

**Alternative plus efficace:**
```easylanguage
CanEnterLong = (condition1) and (condition2) and (condition3);
```

**Raison actuelle:** Lisibilité et debugging facile.

## Gestion des erreurs

### Données insuffisantes

```easylanguage
If CurrentBar > TrendSMAPeriod Then Begin
    SMAValue = Average(Close of Data2, TrendSMAPeriod);
End Else Begin
    SMAValue = Close;  // Fallback
End;
```

Si pas assez de barres pour SMA, utilise prix actuel (filtre désactivé en pratique).

### Data2 manquant

```easylanguage
If UseData2 and CurrentBar > TrendSMAPeriod Then Begin
    SMAValue = Average(Close of Data2, TrendSMAPeriod);
End Else If CurrentBar > TrendSMAPeriod Then Begin
    SMAValue = Average(Close, TrendSMAPeriod);  // Fallback Data1
End
```

Si Data2 non disponible, calcule SMA sur Data1 (Renko).

### Division par zéro

```easylanguage
SharesToTrade = IntPortion((EquityValue * PositionSizeValue) / BrickClose);
```

`BrickClose` ne peut jamais être 0 en pratique (prix d'un instrument).

Si préoccupation:
```easylanguage
If BrickClose > 0 Then
    SharesToTrade = IntPortion((EquityValue * PositionSizeValue) / BrickClose)
Else
    SharesToTrade = 1;
```

## Performance et limites

### Nombre de calculs par brique

Approximativement:
- 10-15 conditions booléennes
- 2-3 calculs de moyenne (SMA)
- 5-10 assignations de variables

**Impact:** Négligeable même sur millions de barres.

### Utilisation mémoire

Variables: ~30 variables × 8 bytes = ~240 bytes

**Impact:** Négligeable.

### Backtesting sur longues périodes

QQQ 1999-2024 (25 ans):
- Renko 1%: ~500-1000 briques
- Calcul: < 1 seconde

**Limitation:** Historique de données disponibles, pas performance code.

### Bar Magnifier

**Importance critique pour:**
- StopIntraday = true
- Précision d'exécution des stops

**Impact performance:**
- Temps de calcul × 2-5
- Mais précision × 10

**Recommandation:** Toujours activé pour backtests finaux.

## Debugging et diagnostic

### Ajouter prints

```easylanguage
Print("CurrentBrickColor: ", CurrentBrickColor);
Print("CanEnterLong: ", CanEnterLong);
Print("SMAValue: ", SMAValue);
```

**Output:** PowerLanguage Editor Output Log

### Visualiser variables

```easylanguage
Plot3(ConsecutiveGreen, "Consecutive Green");
Plot4(ConsecutiveRed, "Consecutive Red");
```

**Output:** Sous-graphiques sur le chart

### Vérifier conditions entrée

Ajouter un plot pour chaque condition:

```easylanguage
Plot5(IIF(IsAboveSMA, 1, 0), "Above SMA");
Plot6(IIF(RequirePriorRed and PreviousBrickColor = "RED", 1, 0), "Prior Red OK");
```

## Extensions futures

### Filtre ADX

```easylanguage
Vars: ADXValue(0);
ADXValue = ADX(14);

// N'entrer que si ADX > 25 (tendance forte)
If ADXValue < 25 Then CanEnterLong = false;
```

### Time-based exit

```easylanguage
Vars: BarsInTrade(0);

// À l'entrée
BarsInTrade = 0;

// Chaque brique
If MarketPosition <> 0 Then BarsInTrade = BarsInTrade + 1;

// Sortie après 20 briques sans nouveau high
If BarsInTrade > 20 and BrickClose <= EntryPrice Then
    Sell("Time Exit") next bar at market;
```

### Pyramiding

```easylanguage
Vars: NumContracts(0);

// Première entrée
If MarketPosition = 0 Then Begin
    Buy SharesToTrade shares;
    NumContracts = 1;
End;

// Ajout
If MarketPosition = 1 and NumContracts < 3 and BrickClose > EntryPrice * 1.02 Then Begin
    Buy SharesToTrade shares;
    NumContracts = NumContracts + 1;
End;
```

## Références

- **MultiCharts Documentation:** https://www.multicharts.com/documentation
- **FlexRenko Guide:** Help > Search "FlexRenko"
- **EasyLanguage Reference:** Help > PowerLanguage Reference Guide
- **Strategy Properties:** Help > Search "Strategy Properties"

---

**Dernière mise à jour:** 2025-11-07
**Version stratégie:** 1.0.0
