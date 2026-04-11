"""Analyse des périodes de crise pour Trend-Parity."""
import pandas as pd
import numpy as np
from strategy import run_backtest_strategy
from framework import compute_metrics, pretty_metrics, load_close

df = run_backtest_strategy()

def metrics_window(start, end, label):
    sub = df.loc[start:end].copy()
    if len(sub) == 0:
        return
    eq = sub["equity"] / sub["equity"].iloc[0]
    qq = sub["qqq"] / sub["qqq"].iloc[0]
    m_strat = compute_metrics(eq)
    m_qqq = compute_metrics(qq)
    days = len(sub)
    years = (sub.index[-1] - sub.index[0]).days / 365.25
    ret_strat = eq.iloc[-1] - 1
    ret_qqq = qq.iloc[-1] - 1
    print(f"\n=== {label}  ({sub.index[0].date()} -> {sub.index[-1].date()}, "
          f"{days} jours, {years:.2f} ans) ===")
    print(f"{'':<22s} {'Return':>10s} {'MaxDD':>10s} {'Vol':>8s} "
          f"{'Sharpe':>8s}")
    print(f"{'Trend-Parity':<22s} {ret_strat*100:>9.2f}% {m_strat.max_dd*100:>9.2f}% "
          f"{m_strat.vol*100:>7.2f}% {m_strat.sharpe:>8.2f}")
    print(f"{'QQQ Buy&Hold':<22s} {ret_qqq*100:>9.2f}% {m_qqq.max_dd*100:>9.2f}% "
          f"{m_qqq.vol*100:>7.2f}% {m_qqq.sharpe:>8.2f}")
    print(f"Outperformance:       {(ret_strat-ret_qqq)*100:>+9.2f} pp")
    # Allocation statistics
    qqq_avg = sub["w_QQQ"].mean() * 100
    ief_avg = sub["w_IEF"].mean() * 100
    gld_avg = sub["w_GLD"].mean() * 100
    bil_avg = sub["w_BIL"].mean() * 100
    qqq_on = (sub["w_QQQ"] > 0.01).mean() * 100
    ief_on = (sub["w_IEF"] > 0.01).mean() * 100
    gld_on = (sub["w_GLD"] > 0.01).mean() * 100
    print(f"Allocation moyenne:   QQQ {qqq_avg:5.1f}%  IEF {ief_avg:5.1f}%  "
          f"GLD {gld_avg:5.1f}%  BIL {bil_avg:6.1f}%")
    print(f"% du temps ON:        QQQ {qqq_on:5.1f}%  IEF {ief_on:5.1f}%  "
          f"GLD {gld_on:5.1f}%")


# Dot-com crash : pic de QQQ mars 2000, creux en octobre 2002
metrics_window("2000-03-01", "2002-10-10", "Dot-com crash (mar 2000 - oct 2002)")

# GFC : pic SPX octobre 2007, creux mars 2009
metrics_window("2007-10-01", "2009-03-09", "GFC (oct 2007 - mars 2009)")

# Cycle complet autour du dot-com (pré-pic à post-recovery)
metrics_window("1999-12-31", "2003-12-31", "Cycle dot-com complet (2000-2003)")

# Cycle complet autour de la GFC
metrics_window("2007-01-01", "2010-12-31", "Cycle GFC complet (2007-2010)")

# Juste pour référence, 2022
metrics_window("2022-01-01", "2022-12-31", "Bear 2022 (actions+obligations)")

# Peak-to-trough de chaque crise en jours
print("\n=== Chronologie des crises ===")
for start, end, label in [
    ("2000-03-01", "2003-01-01", "Dot-com"),
    ("2007-10-01", "2009-04-01", "GFC"),
    ("2020-02-01", "2020-05-01", "Covid"),
    ("2022-01-01", "2023-01-01", "2022"),
]:
    sub = df.loc[start:end]
    if len(sub) == 0:
        continue
    # Strategy DD max and duration
    eq = sub["equity"]
    peak_eq = eq.cummax()
    dd = eq / peak_eq - 1
    trough_date = dd.idxmin()
    peak_date = eq.loc[:trough_date].idxmax()
    recovery = eq.loc[trough_date:]
    recovered = recovery[recovery >= peak_eq.loc[peak_date]]
    recov_date = recovered.index[0] if len(recovered) else None
    # QQQ equivalent
    qq = sub["qqq"]
    qpeak = qq.cummax()
    qdd = qq / qpeak - 1
    qtrough = qdd.idxmin()
    qpeak_date = qq.loc[:qtrough].idxmax()
    qrec = qq.loc[qtrough:]
    qrec_done = qrec[qrec >= qpeak.loc[qpeak_date]]
    qrec_date = qrec_done.index[0] if len(qrec_done) else None

    print(f"\n{label}:")
    print(f"  Trend-Parity: peak {peak_date.date()} -> trough "
          f"{trough_date.date()} ({(trough_date - peak_date).days} j), "
          f"DD {dd.min()*100:.2f}%")
    if recov_date is not None:
        print(f"                recovery {recov_date.date()} "
              f"({(recov_date - trough_date).days} j after trough)")
    print(f"  QQQ:          peak {qpeak_date.date()} -> trough "
          f"{qtrough.date()} ({(qtrough - qpeak_date).days} j), "
          f"DD {qdd.min()*100:.2f}%")
    if qrec_date is not None:
        print(f"                recovery {qrec_date.date()} "
              f"({(qrec_date - qtrough).days} j after trough)")
    else:
        print(f"                recovery: not within window")
