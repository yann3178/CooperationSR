# YANN_RENKO FUNCTIONS - INSTALLATION GUIDE

## 📦 Fichiers de Fonction Requis

Le Signal **RenkoTrendFollowing_v2_Signal** utilise 3 fonctions externes qui doivent être installées séparément dans MultiCharts:

```
YANN_RENKO_CheckLongEntry.txt          - Vérifie conditions d'entrée long
YANN_RENKO_CheckShortEntry.txt         - Vérifie conditions d'entrée short
YANN_RENKO_CalculateTrailingStop.txt   - Calcule niveau de trailing stop
```

## 🚀 Installation des Fonctions

### Étape 1: Ouvrir PowerLanguage Editor

1. Lancer MultiCharts
2. **Format → PowerLanguage Editor** (ou F4)

### Étape 2: Créer les Fonctions

Pour **chaque** fonction (`YANN_RENKO_CheckLongEntry`, `YANN_RENKO_CheckShortEntry`, `YANN_RENKO_CalculateTrailingStop`):

1. **File → New → Function**
2. Copier le contenu du fichier `.txt` correspondant
3. Coller dans l'éditeur
4. **File → Save As**
   - Name: `YANN_RENKO_CheckLongEntry` (ou autre selon la fonction)
   - Description: "Renko strategy entry check function"
5. **Verify** (F5) pour compiler
6. Vérifier qu'il n'y a **aucune erreur**
7. Fermer l'éditeur de fonction

### Étape 3: Vérifier Installation

1. Dans PowerLanguage Editor
2. **Dictionary** tab
3. Chercher "YANN_RENKO"
4. Vous devriez voir les 3 fonctions listées

## ✅ Vérification

Après installation, vous devriez avoir:

```
Functions:
✓ YANN_RENKO_CheckLongEntry
✓ YANN_RENKO_CheckShortEntry
✓ YANN_RENKO_CalculateTrailingStop

Signals:
✓ RenkoTrendFollowing_v2_Signal

Indicators:
✓ RenkoTrendFollowing_v2_Indicator
```

## 📋 Détails des Fonctions

### YANN_RENKO_CheckLongEntry

**Fonction:** Vérifie si toutes les conditions d'entrée LONG sont remplies

**Inputs:**
- `CurrentBrickColor` (Numeric): 1=GREEN, -1=RED, 0=NEUTRAL
- `PreviousBrickColor` (Numeric): Couleur de la brique précédente
- `EntryConfirmType` (String): "FIRST_GREEN" ou "SECOND_GREEN"
- `RequirePriorRed` (True/False): Exiger brique précédente rouge
- `AllowLong` (True/False): Autoriser trades long
- `UseTrendFilter` (True/False): Utiliser filtre de tendance
- `CurrentPrice` (Numeric): Prix de close actuel
- `TrendSMA` (Numeric): Valeur de la SMA de tendance
- `TrendMargin` (Numeric): Marge de tendance (ex: 0.01 pour 1%)

**Return:**
- `True` si signal LONG valide
- `False` sinon

**Logique:**
1. Vérifie que `ALLOW_LONG = true`
2. Vérifie filtre de tendance (si activé): Prix > SMA
3. Vérifie type de confirmation (FIRST_GREEN ou SECOND_GREEN)
4. Vérifie condition prior red (si requis)
5. Retourne true si toutes conditions OK

---

### YANN_RENKO_CheckShortEntry

**Fonction:** Vérifie si toutes les conditions d'entrée SHORT sont remplies

**Inputs:**
- `CurrentBrickColor` (Numeric): 1=GREEN, -1=RED, 0=NEUTRAL
- `PreviousBrickColor` (Numeric): Couleur de la brique précédente
- `EntryConfirmType` (String): "FIRST_GREEN" ou "SECOND_GREEN"
- `RequirePriorRed` (True/False): Exiger brique précédente verte (inverse pour short)
- `AllowShort` (True/False): Autoriser trades short
- `UseTrendFilter` (True/False): Utiliser filtre de tendance
- `CurrentPrice` (Numeric): Prix de close actuel
- `TrendSMA` (Numeric): Valeur de la SMA de tendance
- `TrendMargin` (Numeric): Marge de tendance (ex: 0.01 pour 1%)

**Return:**
- `True` si signal SHORT valide
- `False` sinon

**Logique:**
1. Vérifie que `ALLOW_SHORT = true`
2. Vérifie filtre de tendance (si activé): Prix < SMA
3. Vérifie type de confirmation (FIRST_RED ou SECOND_RED)
4. Vérifie condition prior green (si requis)
5. Retourne true si toutes conditions OK

---

### YANN_RENKO_CalculateTrailingStop

**Fonction:** Calcule le nouveau niveau de trailing stop

**Inputs:**
- `PositionDir` (Numeric): 1=LONG, -1=SHORT, 0=FLAT
- `CurrentStopLevel` (Numeric): Niveau de stop actuel
- `CurrentBrickClose` (Numeric): Close de la brique actuelle
- `PreviousBrickClose` (Numeric): Close de la brique précédente
- `CurrentBrickColor` (Numeric): 1=GREEN, -1=RED, 0=NEUTRAL
- `StopTrail` (True/False): Trailing stop activé
- `StopType` (String): "PREVIOUS_BRICK", "FIXED_PERCENT", etc.

**Return:**
- Nouveau niveau de stop (Numeric)

**Logique:**
1. Si `StopTrail = false` → retourne stop actuel (inchangé)
2. Si `StopType <> "PREVIOUS_BRICK"` → retourne stop actuel
3. **Pour LONG:** Si brique GREEN → trail stop UP (max du stop actuel et previous brick close)
4. **Pour SHORT:** Si brique RED → trail stop DOWN (min du stop actuel et previous brick close)
5. Retourne nouveau niveau de stop

---

## ⚠️ Points Importants

### 1. Nommage Strict

Les noms des fonctions **DOIVENT** être exactement:
- `YANN_RENKO_CheckLongEntry` (pas `YANN_RENKO_CheckLongEntry_v2` ou autre)
- `YANN_RENKO_CheckShortEntry`
- `YANN_RENKO_CalculateTrailingStop`

Le Signal cherche ces noms précis. Tout écart causera une erreur de compilation.

### 2. Ordre d'Installation

**Installation OBLIGATOIRE dans cet ordre:**

1. **D'abord:** Installer les 3 fonctions
2. **Ensuite:** Installer le Signal
3. **Enfin:** Installer l'Indicator (optionnel)

Si vous installez le Signal AVANT les fonctions → **Erreur de compilation!**

### 3. Types de Données

Les fonctions utilisent des types spécifiques:
- `NumericSimple`: Pour les nombres
- `StringSimple`: Pour les strings
- `TrueFalse`: Pour les booléens

**Ne pas modifier** ces types, sinon incompatibilité avec le Signal.

### 4. Modification des Fonctions

Si vous modifiez une fonction:
1. **Verify** (F5) pour compiler
2. **Format Signal → Verify** pour recompiler le Signal
3. Reload le chart

Le Signal ne se met pas à jour automatiquement.

---

## 🐛 Troubleshooting

### Erreur: "Function Not Found"

**Message:**
```
Undeclared identifier YANN_RENKO_CheckLongEntry
```

**Cause:** Fonction pas installée ou nom incorrect

**Solution:**
1. Ouvrir PowerLanguage Editor
2. Dictionary → Functions
3. Chercher "YANN_RENKO"
4. Si absent → installer la fonction
5. Si nom différent → corriger le nom exactement

---

### Erreur: "Type Mismatch"

**Message:**
```
Type mismatch in function call
```

**Cause:** Arguments passés avec mauvais type

**Solution:**
1. Vérifier que les types des inputs correspondent
2. NumericSimple pour nombres
3. StringSimple pour strings (avec guillemets)
4. TrueFalse pour booléens

---

### Fonction Modifiée Mais Signal Inchangé

**Symptôme:** Vous modifiez la fonction mais le Signal utilise l'ancienne version

**Solution:**
1. Recompiler la fonction (F5)
2. **Format Signal → Verify** (recompiler le Signal)
3. Remove Signal du chart
4. Réappliquer le Signal
5. Reload le chart

---

## 📖 Exemple d'Utilisation dans le Signal

Voici comment le Signal appelle les fonctions:

```easylanguage
// Check LONG entry
LongSignal = YANN_RENKO_CheckLongEntry(
    CurrentBrick_Color,        // 1, -1, ou 0
    PreviousBrick_Color,       // 1, -1, ou 0
    ENTRY_CONFIRM_TYPE,        // "FIRST_GREEN" ou "SECOND_GREEN"
    REQUIRE_PRIOR_RED,         // true ou false
    ALLOW_LONG,                // true ou false
    USE_TREND_FILTER,          // true ou false
    Close,                     // Prix actuel
    SMAValue,                  // Valeur SMA calculée
    TREND_MARGIN);             // 0.00, 0.01, etc.

// Check SHORT entry
ShortSignal = YANN_RENKO_CheckShortEntry(
    CurrentBrick_Color,
    PreviousBrick_Color,
    ENTRY_CONFIRM_TYPE,
    REQUIRE_PRIOR_RED,
    ALLOW_SHORT,
    USE_TREND_FILTER,
    Close,
    SMAValue,
    TREND_MARGIN);

// Calculate trailing stop
NewStopLevel = YANN_RENKO_CalculateTrailingStop(
    PositionDirection,         // 1, -1, ou 0
    StopLevel,                 // Stop actuel
    CurrentBrick_Close,        // Close de la brique
    PreviousBrick_Close,       // Close brique précédente
    CurrentBrick_Color,        // 1, -1, ou 0
    STOP_TRAIL,                // true ou false
    STOP_TYPE);                // "PREVIOUS_BRICK", etc.
```

---

## ✅ Checklist d'Installation Complète

Avant d'utiliser le Signal, vérifier:

- [ ] `YANN_RENKO_CheckLongEntry` installé et compilé (F5 OK)
- [ ] `YANN_RENKO_CheckShortEntry` installé et compilé (F5 OK)
- [ ] `YANN_RENKO_CalculateTrailingStop` installé et compilé (F5 OK)
- [ ] Les 3 fonctions visibles dans Dictionary
- [ ] `RenkoTrendFollowing_v2_Signal` installé
- [ ] Signal compile sans erreur (Verify OK)
- [ ] `RenkoTrendFollowing_v2_Indicator` installé (optionnel)

---

## 📚 Documentation Complémentaire

Pour plus de détails sur l'utilisation du Signal et de l'Indicator:
- **README_v2.md**: Documentation complète de la stratégie
- **TESTING_GUIDE.md**: Guide de validation
- **MIGRATION_GUIDE.md**: Migration depuis v1.0

---

**Version:** 2.0.1
**Date:** 2025-11-08
**Compatibilité:** MultiCharts 32-bit & 64-bit, PowerLanguage
