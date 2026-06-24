"""
Test d'edge statistique : agregation des trades WEEKLY sur tous les futures
indices backtestes (NQ, ES, YM, DAX, CAC, IBEX).

Probleme adresse : sur un seul future, le weekly genere 4-6 trades -> trop
peu pour conclure. En agregeant tous les futures on augmente N. Mais les
indices sont fortement correles : on mesure donc aussi cet effet.

Normalisation : chaque trade est ramene a son rendement % (exit/entry - 1),
independant de la devise et de la valeur du point (long uniquement).
"""

import numpy as np
import pandas as pd
from scipy import stats as st

import backtest_rizzie as bt

FUTURES = ["NQ", "ES", "YM", "DAX", "CAC", "IBEX"]   # indices futures seulement
INTERVAL = "1wk"


def trades_for(inst_key):
    inst = bt.INSTRUMENTS[inst_key]
    df = bt.load_data(inst["ticker"], INTERVAL)
    df = bt.add_bollinger(df)
    df = bt.add_adx(df, bt.ADX_PERIOD)
    df = bt.add_swings(df)
    _, trades, _ = bt.run_backtest(df, inst["point"])
    if len(trades):
        trades = trades.copy()
        trades["ret"] = trades["exit_price"] / trades["entry_price"] - 1.0
        trades["inst"] = inst_key
    return trades


def describe(name, rets):
    rets = np.asarray(rets, dtype=float)
    n = len(rets)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    win_rate = len(wins) / n * 100 if n else 0
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
    mean = rets.mean() if n else 0
    sd = rets.std(ddof=1) if n > 1 else float("nan")
    # Test t unilateral : moyenne des rendements > 0 ?
    if n > 1 and sd > 0:
        t, p_two = st.ttest_1samp(rets, 0.0)
        p_one = p_two / 2 if t > 0 else 1 - p_two / 2
    else:
        t, p_one = float("nan"), float("nan")
    print(f"  {name:18} N={n:3d}  WinRate={win_rate:5.1f}%  "
          f"PF={pf:5.2f}  ret_moyen={mean*100:+6.2f}%  "
          f"t={t:5.2f}  p(1-tail)={p_one:.4f}")
    return rets


def main():
    print("Chargement des trades weekly par future...\n")
    per_inst = {}
    all_trades = []
    for k in FUTURES:
        t = trades_for(k)
        per_inst[k] = t
        if len(t):
            all_trades.append(t)
    pooled = pd.concat(all_trades, ignore_index=True)

    print("=" * 78)
    print("  RENDEMENTS PAR TRADE (weekly) - par instrument")
    print("=" * 78)
    for k in FUTURES:
        describe(k, per_inst[k]["ret"])

    print("\n" + "=" * 78)
    print("  POOL AGREGE (tous futures indices, weekly)")
    print("=" * 78)
    describe("POOL", pooled["ret"])

    # --- Effet de la correlation : combien d'evenements reellement independants ? ---
    print("\n" + "=" * 78)
    print("  CORRELATION INTER-INSTRUMENTS (chevauchement temporel des trades)")
    print("=" * 78)
    # Annee d'entree de chaque trade, pour voir si les gains/pertes se concentrent
    pooled["entry_year"] = pd.to_datetime(pooled["entry_date"]).dt.year
    by_year = pooled.groupby("entry_year")["ret"].agg(["count", "mean"])
    by_year["mean"] = (by_year["mean"] * 100).round(2)
    print(by_year.to_string())
    print(f"\n  -> {len(pooled)} trades repartis sur seulement "
          f"{pooled['entry_year'].nunique()} annees calendaires.")

    # Concentration : part du PnL total (somme des rendements) due au top trade
    rets = np.sort(pooled["ret"].to_numpy())[::-1]
    tot = rets[rets > 0].sum()
    print(f"  -> Top 1 trade = {rets[0]/tot*100:4.1f}% du gain brut total ; "
          f"Top 3 = {rets[:3][rets[:3]>0].sum()/tot*100:4.1f}%.")

    # Bootstrap par blocs (par instrument) pour intervalle de confiance robuste
    rng = np.random.default_rng(42)
    means = []
    groups = [per_inst[k]["ret"].to_numpy() for k in FUTURES if len(per_inst[k])]
    for _ in range(20000):
        # re-echantillonne des INSTRUMENTS entiers (respecte la dependance intra)
        sample = np.concatenate(
            [groups[i] for i in rng.integers(0, len(groups), len(groups))])
        means.append(sample.mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    print("\n" + "=" * 78)
    print("  BOOTSTRAP PAR BLOCS-INSTRUMENTS (20000 tirages)")
    print("=" * 78)
    print(f"  Rendement moyen par trade : {pooled['ret'].mean()*100:+.2f}%")
    print(f"  IC 95% (bloc-bootstrap)   : [{lo*100:+.2f}% ; {hi*100:+.2f}%]")
    print(f"  -> edge { 'CONFIRME (IC>0)' if lo>0 else 'NON confirme (IC contient 0)'}")


if __name__ == "__main__":
    main()
