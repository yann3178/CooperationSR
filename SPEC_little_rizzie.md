# Spécification — Stratégie "Little Rizzie" (Marci Silfrain)

## Vue d'ensemble
Stratégie **long uniquement**, de type **retournement haussier après extension baissière**, confirmée par une **cassure de structure** (Break of Structure). Elle achète quand le marché, après être tombé en survente sous sa bande de Bollinger dans une structure baissière, **reprend la main** en cassant son dernier sommet — le tout filtré par la **force de tendance (ADX)** et, en option, une **confluence Fibonacci**.

---

## 1. Indicateurs

**Bandes de Bollinger** (sur le `Close`)
```
BB_mid   = SMA(Close, 20)
BB_upper = BB_mid + 2.0 × STD(Close, 20)
BB_lower = BB_mid − 2.0 × STD(Close, 20)
```

**Swings / pivots** (fenêtre centrée de `SWING_WINDOW` barres, `k = (SWING_WINDOW−1)//2`)
- Barre `i` = **swing high** si `High[i]` est le **maximum strict** de la fenêtre `[i−k, i+k]`.
- Barre `i` = **swing low** si `Low[i]` est le **minimum strict** de `[i−k, i+k]`.
- **Anti-lookahead (essentiel)** : un pivot en `i` n'est confirmé qu'à `i+k`. On **décale les niveaux de `k` barres** (`shift(k)`) puis on **propage** (`ffill`) → à chaque barre on dispose du `last_swing_high` / `last_swing_low` réellement connus à ce moment.

**ADX** : période 14, **lissage de Wilder** (DI+/DI− → DX → ADX).

---

## 2. Machine à états de la structure de marché

Deux états : `bull` / `bear`, plus un flag `bb_breach`.

| Événement | Transition |
|---|---|
| `Close` clôture **sous** `last_swing_low` | structure → **bear**, `bb_breach` = False |
| Structure = bear **et** `Close ≤ BB_lower` | `bb_breach` = **True** (mémorisé) |
| Entrée déclenchée (cassure haussière) | structure → **bull**, `bb_breach` = False |

> `bb_breach` enregistre le fait qu'**au moins une clôture est passée sous la bande basse depuis le début de la phase baissière en cours**.

---

## 3. Condition d'ENTRÉE (achat de 1 contrat au `Close`)

**Toutes** ces conditions doivent être réunies sur la barre courante :

1. **Structure baissière** en cours (`state == bear`).
2. **`bb_breach == True`** (clôture sous la bande inférieure survenue durant cette phase baissière).
3. **Break of Structure haussier** : `Close > last_swing_high`.
4. **ADX(14) > 20** (filtre de force de tendance).
5. **(Optionnel) Confluence Fibonacci** validée (voir §5).

À l'entrée : structure → **bull**, `bb_breach` réinitialisé.

---

## 4. Condition de SORTIE (trailing stop structurel)

- On clôture la position dès que **`Close < last_swing_low`**.
- Cet événement refait basculer la structure en **bear** (le cycle peut recommencer).
- Pas de stop fixe ni de take-profit : la sortie suit la **structure de prix** (le dernier creux validé monte au fil de la tendance → stop suiveur).

---

## 5. Filtre de Confluence Fibonacci (facultatif, `USE_FIB_FILTER`)

1. **Macro bull run** : sur une fenêtre glissante de **`MACRO_LOOKBACK` barres** (voir §6 — exprimée **en nombre de barres**, passé uniquement), identifier `Macro_Low` (plus bas absolu) et `Macro_High` (plus haut absolu). **Valider la dynamique haussière uniquement si `Macro_High` survient APRÈS `Macro_Low`.**
2. **Niveaux de retracement** de l'impulsion : `niveau_r = Macro_High − r × (Macro_High − Macro_Low)` pour `r ∈ {0.382, 0.5, 0.618}`.
3. **Cible Rizzie** (projection baissière du motif) :
   ```
   D      = last_swing_high − last_swing_low
   target = last_swing_low − D     (= 2×last_swing_low − last_swing_high)
   ```
4. **Confluence** : valide si la cible tombe dans la bande de tolérance d'au moins un niveau :
   ```
   |target − niveau_r| / niveau_r  ≤  FIB_TOLERANCE_PCT / 100
   ```

> **Rôle du filtre** : il **n'augmente pas le rendement brut** mais **réduit fortement le drawdown** et **stabilise** la stratégie (moindre sensibilité aux autres paramètres). Contrepartie : il est **sélectif** (moins de trades).

---

## 6. Macro lookback — EXPRIMÉ EN NOMBRE DE BARRES (auto-similaire)

**Principe (évolution clé) :** la fenêtre macro du filtre Fibonacci est définie en **nombre de barres** (`MACRO_LOOKBACK`), **et non en durée calendaire**. Elle est ainsi **auto-similaire (fractale)** d'un timeframe à l'autre : la référence Fib reste toujours proportionnelle à l'horizon de trading.

| TF tradé | `MACRO_LOOKBACK` ≈ 200 barres correspond à… |
|---|---|
| Weekly | ~4 ans |
| Daily | ~10 mois |
| 4 H | ~6 semaines |
| 1 H | ~2-3 semaines |
| 15 min | ~3-4 jours |
| 5 min | ~1-2 jours |

**Pourquoi pas une durée calendaire fixe (ex. 12 mois) ?** Cela rendait le filtre absurde/inopérant en intraday (sur 4H, 1 an de warmup faisait chuter l'échantillon à 3-8 trades). Le raisonnement en barres restaure des échantillons exploitables sur tous les timeframes.

**À optimiser, ne pas deviner.** Comme `SWING_WINDOW` et `FIB_TOLERANCE_PCT`, `MACRO_LOOKBACK` se règle en **cherchant un plateau de robustesse** (balayage du nombre de barres), par marché et par timeframe. *Constat empirique sur NQ Daily : un macro court (~80-100 barres) surpasse nettement ~250 barres (PF ~6 vs ~3,5, DD −17 % vs −28 %) → 12 mois était bien trop restrictif.*

---

## 7. Paramètres

| Paramètre | Valeur | Statut |
|---|---|---|
| BB période / écart-type | 20 / 2.0 | fixe |
| ADX période / seuil | 14 / 20 | fixe |
| Niveaux Fibonacci | 38,2 / 50 / 61,8 % | fixe |
| `SWING_WINDOW` | **5** (Daily/Weekly), **9** (4H) | ↑ quand le TF descend (plus de bruit) ; à ré-optimiser pour 1h/15m/5m |
| `FIB_TOLERANCE_PCT` | par actif : NQ 3,0 · ES 3,0 · YM 3,0 · DAX 1,5 · CAC 1,0 · IBEX 3,0 | à ré-optimiser par actif/TF |
| `MACRO_LOOKBACK` | **en barres, défaut 200** (≈100 préférable en Daily) | auto-similaire ; à optimiser par actif/TF |
| `USE_FIB_FILTER` | True / False | active le §5 |

---

## 8. Money management / comptabilité

- **Capital initial** : 100 000.
- **Taille** : 1 contrat (pas de pyramidage), **une seule position** à la fois.
- **PnL** = `(prix_sortie − prix_entrée) × valeur_du_point × contrats`.
- **Valeur du point** (par marché) : NQ 20 $ · ES 50 $ · YM 5 $ · FDAX 25 € · FCE (CAC) 10 € · IBEX 10 €.
- **Équité** marquée au marché (mark-to-market) à chaque barre pour le calcul du **Max Drawdown**.

---

## 9. Résumé en une phrase

> *Dans une structure baissière où le prix a clôturé sous sa bande de Bollinger inférieure, acheter à la clôture quand le prix casse au-dessus de son dernier sommet validé avec un ADX > 20 (et, en option, quand la cible baissière théorique coïncide — à `FIB_TOLERANCE_PCT` % près — avec un niveau de Fibonacci d'un macro bull run mesuré sur `MACRO_LOOKBACK` barres) ; sortir quand le prix clôture sous son dernier creux validé.*
