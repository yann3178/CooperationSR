# Prompt pour Claude Code local — Backtest & robustesse "Little Rizzie"

> **Rôle :** Tu es un développeur quantitatif senior expert en trading algorithmique, backtesting et validation statistique de stratégies. Tu as accès à un moteur de backtest interne et à des historiques **longs** sur l'ensemble des marchés **futures** et sur **tous les timeframes**.

> **Mission :** Implémenter, backtester et **éprouver la robustesse** de la stratégie long-only **"Little Rizzie" (méthode Marci Silfrain)** sur plusieurs marchés futures et plusieurs timeframes : **5 min, 15 min, 1 h, 4 h, Daily, Weekly**. L'objectif n'est PAS d'afficher la meilleure performance possible, mais de déterminer **où et à quelles conditions un edge réel et robuste existe**, en évitant la sur-optimisation.

---

## 1. Règles exactes de la stratégie (long uniquement)

**Indicateurs :**
- **Bandes de Bollinger** : période 20, écart-type 2.0, sur le **close**.
- **Swings (pivots)** : sur une fenêtre **centrée** de `SWING_WINDOW` barres. Avec `k = (SWING_WINDOW - 1) // 2` barres de confirmation de chaque côté. Une barre `i` est un **swing high** si son `High` est le **maximum strict** de `[i-k, i+k]` (idem `swing low` avec le `Low` minimum strict).
- **ADX** : période 14, **lissage de Wilder**.

**⚠️ Gestion stricte du lookahead bias :** un pivot détecté en barre `i` n'est confirmé qu'à la barre `i+k`. Il faut donc **décaler les niveaux de swing de `k` barres** (`shift(k)`) puis propager (`ffill`) le **dernier swing validé connu**. Ne jamais utiliser un swing avant sa barre de confirmation.

**État de structure de marché :**
- La structure passe **baissière** dès qu'un **close** clôture **sous le dernier swing low validé**.
- Pendant la phase baissière, on mémorise un flag `bb_breach` = vrai dès qu'un **close clôture sous la bande de Bollinger inférieure** (crossover en clôture).

**Condition d'ENTRÉE (achat de 1 contrat au close) — toutes requises :**
1. Structure **baissière** en cours.
2. `bb_breach` = vrai (clôture sous bande basse survenue depuis le début de la phase baissière).
3. **Break of Structure haussier** : le `close` du jour **casse au-dessus du dernier swing high validé**.
4. **ADX(14) > 20** (filtre de force de tendance).
5. **(Optionnel)** **Filtre de Confluence Fibonacci** (voir §2).

À l'entrée, la structure rebascule en **haussière** et `bb_breach` est réinitialisé.

**Condition de SORTIE (trailing stop structurel) :**
- On clôture la position si le **close** passe **sous le dernier swing low validé**. Cet événement refait basculer la structure en baissière.

**Position sizing :** 1 contrat, capital initial 100 000, valeur du point propre à chaque future. Pas de pyramidage. Une seule position à la fois.

---

## 2. Filtre de Confluence Fibonacci (facultatif, `USE_FIB_FILTER`)

1. **Macro bull run** : sur une fenêtre glissante longue **≈ 1 an calendaire** (voir §3, adaptatif au timeframe), passé uniquement, identifier `Macro_Low` (plus bas absolu) et `Macro_High` (plus haut absolu). Valider la dynamique haussière **uniquement si le Macro_High survient APRÈS le Macro_Low**.
2. **Niveaux de retracement** de l'impulsion : `niveau = Macro_High - r * (Macro_High - Macro_Low)` pour `r ∈ {0.382, 0.5, 0.618}`.
3. **Cible Rizzie** (projection baissière) : `D = SwingHigh - SwingLow`, reportée sous le swing low → `target = SwingLow - D` (= `2*SwingLow - SwingHigh`).
4. **Confluence** : la condition est validée **uniquement** si la cible Rizzie tombe à **±`FIB_TOLERANCE_PCT` %** d'au moins un des trois niveaux de Fibonacci (`|target - niveau| / niveau ≤ FIB_TOLERANCE_PCT/100`).

---

## 3. Paramètres (point de départ — à RE-OPTIMISER par marché et par timeframe)

| Paramètre | Valeur de départ | Remarque |
|---|---|---|
| BB période / std | 20 / 2.0 | fixe |
| ADX période / seuil | 14 / 20 | fixe |
| Niveaux Fib | 38.2 / 50 / 61.8 % | fixe |
| `SWING_WINDOW` | **Daily/Weekly : 5 ; 4H : 9** | **doit augmenter quand le timeframe descend** (plus de bruit → fenêtre plus large). À ré-optimiser pour 1h/15m/5m. |
| `FIB_TOLERANCE_PCT` | **par actif** : NQ 3.0, ES 3.0, YM 3.0, DAX 1.5, CAC 1.0, IBEX 3.0 | à ré-optimiser par actif **et** par timeframe |
| Macro lookback | **≈ 365 jours calendaires, ADAPTATIF** | convertir en nombre de barres selon le timeframe (daily≈252, weekly≈52, 4h≈1500, 1h≈6000, etc.). **Ne jamais coder "252 barres" en dur** : sur intraday cela ne représente que quelques jours. |

**Important :** ces valeurs proviennent d'une étude sur données Yahoo (historique court, surtout en intraday). Avec ton historique long, **ré-optimise tout proprement** et ne présuppose pas que ces valeurs tiennent.

---

## 4. Marchés et timeframes à tester

- **Marchés futures** : au minimum les indices **NQ, ES, YM, RTY (Russell), DAX (FDAX), CAC (FCE), IBEX, EuroStoxx 50, Nikkei**. Ajoute si dispo : **taux (Bund, ZN/ZB), matières premières (GC or, CL pétrole), FX (6E, 6B)** — utile pour couvrir un **large spectre de volatilité**.
- **Timeframes** : **5 min, 15 min, 1 h, 4 h, Daily, Weekly**.
- Utilise les **vrais contrats futures** (continus, back-adjusted / roll géré proprement), pas des proxies indices. Précise la méthode de roll.

---

## 5. Méthodologie de robustesse (CRUCIAL — c'est le cœur de la mission)

Applique une discipline anti-surajustement stricte :

1. **Recherche de PLATEAU, pas de pic.** Pour chaque paramètre balayé (`SWING_WINDOW`, `FIB_TOLERANCE_PCT`), produis une courbe/table de performance. Ne retiens un réglage que s'il se situe dans une **plage contiguë et stable** (transitions douces entre voisins). **Rejette explicitement** : les pics isolés, les pics en **bordure** de la plage testée, et tout réglage reposant sur **trop peu de trades**.
2. **Seuil de significativité** : signale tout résultat basé sur **< ~30 trades** comme non concluant. Méfie-toi des Profit Factor « ∞ » (aucun perdant) ou « 0 » (aucun gagnant) = échantillon trop petit.
3. **Normalisation inter-marchés** : pour agréger/comparer des marchés de devises et valeurs de point différentes, raisonne en **rendement % par trade** (ou en multiples de R / ATR), pas en cash brut.
4. **Corrélation** : si tu agrèges plusieurs marchés (ex. tous les indices) pour gonfler l'échantillon, **corrige la dépendance** (les indices sont très corrélés → l'échantillon effectif est bien plus petit que le nombre de trades). Utilise un **block-bootstrap par marché** et reporte un **intervalle de confiance** ; conclus à un edge seulement si l'IC exclut 0.
5. **Out-of-sample / Walk-forward** : optimise sur une période, valide sur une période **hors échantillon** distincte. Reporte la dégradation in-sample → out-of-sample.
6. **Calibration volatilité↔tolérance** : teste l'hypothèse « `FIB_TOLERANCE_PCT` optimal ∝ volatilité de l'actif ». Mesure la volatilité (vol annualisée des rendements et ATR% médian), et vérifie si la tolérance robuste scale avec elle **sur un large spectre de volatilité** (c'est pour ça qu'il faut inclure taux, or, FX, voire crypto). Si une relation nette existe, propose une formule `tol = f(vol)`.
7. **Coûts réalistes** : intègre **commissions + slippage** par contrat (le slippage pénalise surtout les bas timeframes 5m/15m, à fréquence élevée). Reporte les résultats nets de coûts.
8. **Pas de troncature silencieuse** : si tu limites la couverture (top-N, échantillonnage), dis-le.

---

## 6. Livrables attendus

1. Le **code** du backtest (modulaire, paramétrable, sans lookahead).
2. Pour **chaque (marché × timeframe)** : capital final, profit net, **nb de trades, Win Rate, Profit Factor, Max Drawdown ($ et %), expectancy par trade, Sharpe & Sortino, durée moyenne des trades**, le tout **net de coûts**.
3. Les **tables/heatmaps d'optimisation** (plateaux) pour `SWING_WINDOW` et `FIB_TOLERANCE_PCT`, par marché et timeframe, avec ta lecture (plateau vs pic).
4. Les résultats **walk-forward** (in-sample vs out-of-sample).
5. Une **synthèse exécutive** : sur **quels marchés et quels timeframes l'edge est réel et robuste**, lesquels sont à écarter, et les **paramètres recommandés par marché/timeframe**. Sois **honnête et critique** : signale les résultats flatteurs mais non significatifs.

---

## 7. Hypothèses connues à valider (issues d'une première étude sur données courtes)

- La stratégie semble **meilleure en Daily** sur indices tendanciels (NQ en tête) ; **ES et BTC échouaient**. À reconfirmer sur historique long.
- Le **filtre Fibonacci** apportait surtout un **contrôle du drawdown** (pas du rendement brut) et stabilisait la sensibilité au paramètre swing — mais il devient **très sélectif** (peu de trades) avec une vraie fenêtre macro d'1 an, surtout en intraday. Vérifie s'il reste exploitable en 5m/15m/1h avec ton historique long.
- Le **Weekly** manquait cruellement de trades → conclusions non fiables. Avec un historique long, réévalue.

**Commence par implémenter et valider la logique sur un marché/timeframe de référence (NQ Daily), confirme l'absence de lookahead, puis déroule la grille complète marchés × timeframes avec la méthodologie de robustesse du §5.**
