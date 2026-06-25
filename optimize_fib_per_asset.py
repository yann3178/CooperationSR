"""
Optimisation de la tolerance Fibonacci PAR ACTIF (daily, swing window = 5),
avec mise en relation de la tolerance robuste et de la VOLATILITE de l'actif.

Idee : un actif plus volatil a des oscillations de prix plus larges -> la cible
Rizzie a besoin d'une bande de tolerance plus large pour entrer en confluence
avec un niveau de Fibonacci. On cherche donc si la tolerance optimale scale
avec la volatilite, pour la calibrer automatiquement.
"""

import numpy as np
import pandas as pd

import backtest_rizzie as bt

ASSETS = ["NQ", "ES", "YM", "DAX", "CAC", "IBEX"]   # futures indices
INTERVAL = "1d"
TOLS = [round(0.5 * i, 1) for i in range(1, 11)]     # 0.5 .. 5.0


def volatility_metrics(df):
    """Vol annualisee des rendements + ATR% median (mesures de volatilite)."""
    ret = np.log(df["Close"] / df["Close"].shift(1)).dropna()
    ann_vol = ret.std(ddof=0) * np.sqrt(252) * 100.0
    # ATR(14) en % du prix
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    atr_pct = (atr / c * 100.0).median()
    return ann_vol, atr_pct


def robust_tol(rows):
    """
    Heuristique de plateau : on cherche la tolerance au centre de la plus
    longue plage contigue ou PF >= 1.5 ET DD% >= -50 (variation douce).
    Renvoie (tol_recommandee, pf, dd, n_trades) ou None si pas de plateau.
    """
    ok = [r for r in rows]
    best_run, cur = [], []
    for r in rows:
        good = (r["pf"] >= 1.5) and (r["dd_pct"] >= -50) and (r["n_trades"] >= 8)
        if good:
            cur.append(r)
            if len(cur) > len(best_run):
                best_run = cur[:]
        else:
            cur = []
    if not best_run:
        return None
    mid = best_run[len(best_run) // 2]
    return mid["tol"], mid["pf"], mid["dd_pct"], mid["n_trades"], len(best_run)


def main():
    summary = []
    for a in ASSETS:
        df, inst, _ = bt.prepare(a, INTERVAL)
        ann_vol, atr_pct = volatility_metrics(df)
        # sweep de tolerance (reutilise la logique du backtest)
        rows = []
        for tol in TOLS:
            fc, tr, eq = bt.run_backtest(df, inst["point"], use_fib=True, fib_tol=tol)
            s = bt.compute_stats(fc, tr, eq)
            s["tol"] = tol
            rows.append(s)
        # affichage tableau par actif
        print("\n" + "=" * 76)
        print(f"  {inst['name']}  | vol annuelle={ann_vol:.1f}%  ATR%~{atr_pct:.2f}%")
        print("=" * 76)
        print(f"  {'Tol%':>5} | {'Trades':>6} | {'WinR':>5} | {'PF':>6} | {'DD%':>7}")
        print("  " + "-" * 44)
        for r in rows:
            print(f"  {r['tol']:>5.1f} | {r['n_trades']:>6} | {r['win_rate']:>4.0f}% |"
                  f" {r['pf']:>6.2f} | {r['dd_pct']:>6.1f}%")
        rec = robust_tol(rows)
        summary.append((a, inst["name"], ann_vol, atr_pct, rec))

    # synthese volatilite <-> tolerance robuste
    print("\n" + "#" * 76)
    print("  SYNTHESE : tolerance robuste vs volatilite")
    print("#" * 76)
    print(f"  {'Actif':6} | {'VolAnn%':>7} | {'ATR%':>5} | {'Tol reco':>8} | "
          f"{'PF':>5} | {'DD%':>6} | {'#tr':>4} | {'largeur plateau':>14}")
    print("  " + "-" * 74)
    for a, name, vol, atr, rec in summary:
        if rec:
            tol, pf, dd, n, width = rec
            print(f"  {a:6} | {vol:>7.1f} | {atr:>5.2f} | {tol:>7.1f}% | "
                  f"{pf:>5.2f} | {dd:>5.1f}% | {n:>4} | {width} pas")
        else:
            print(f"  {a:6} | {vol:>7.1f} | {atr:>5.2f} | {'aucun plateau':>8}")


if __name__ == "__main__":
    main()
