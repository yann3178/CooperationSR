# Addendum — Kevin Davey's monthly breakout algorithm

> Follow-up to `strategy_report.md` in response to the question:
> *Kevin Davey a appliqué cet algorithme en EasyLanguage aux ETF
> SPY, XLF, EEM, GLD, USO et a obtenu des résultats bons.  Peux-tu
> ajouter ces scénarios et voir si tu arrives à améliorer les résultats ?*

## The algorithm

```
input: x1(4), x2(5);
var:  nshares(1);
nshares = 100;
If date >= 1061229 and c[0] - c[x1] >= 0 and marketposition = 0
    then buy nshares shares next bar at market;
If c[0] - c[x2] < 0 then sell next bar at market;
If lastbaronchart then sell this bar at close;
```

Timeframe: **monthly** → `x1 = 4` and `x2 = 5` are lookbacks in months.

Translation:
* **Entry** (if flat): at month-end `t`, if `close[t] >= close[t-4]`, go
  long at the next month's first trading day.
* **Exit**: if `close[t] < close[t-5]`, exit at the next month's first
  trading day.

Start date `1061229` = **2006-12-29** in TradeStation YY/MM/DD.

## Implementations tested

Code: `davey_strategy.py`, `davey_variants.py`, `davey_on_tp.py`,
`davey_final.py`.

| ID   | Universe                                        | Allocation rule            |
| ---- | ------------------------------------------------ | -------------------------- |
| V1   | SPY, XLF, EEM, GLD, USO                          | 20 % fixed per ETF when long, rest in BIL (original Davey port) |
| V2   | SPY, XLF, EEM, GLD, USO                          | 1/k equal weight among active legs (full-budget when any active) |
| V3   | SPY, QQQ, XLF, EEM, EFA, IWM, GLD, TLT, IEF, DBC | 1/k equal weight |
| V4   | V3 with QLD swapped for QQQ                      | 1/k equal weight |
| V5   | V3                                               | inverse-vol weighted |
| V5c  | V4                                               | inverse-vol weighted |

Plus several head-to-head gate substitutions on Trend-Parity's own
universe (QQQ/IEF/GLD) where only the trend filter is swapped from
SMA-150 to Davey's monthly breakout.

## Results on Davey's original 5-ETF universe (2007-01 → 2026-04)

| Configuration            | CAGR   | Vol    | Sharpe | MaxDD    | Calmar |
| ------------------------ | -----: | -----: | -----: | -------: | -----: |
| **V1 Davey 20 % fixed**  | 5.50 % | 12.6 % | 0.49   | −34.6 %  |  0.16  |
| V2 1/k eq-active         | 5.18 % | 17.4 % | 0.38   | −49.1 %  |  0.11  |
| V3 10-ETF 1/k eq         | 6.99 % | 13.2 % | 0.58   | −30.7 %  |  0.23  |
| V4 V3 + QLD leverage     | 7.77 % | 15.1 % | 0.57   | −35.2 %  |  0.22  |
| V5 10-ETF inv-vol        | 5.73 % | 11.1 % | 0.56   | −26.4 %  |  0.22  |
| V5c V5 + QLD             | 5.88 % | 11.6 % | 0.55   | −26.4 %  |  0.22  |
| *QQQ buy & hold*         | 15.66 % | 22.2 % | 0.77 | −53.4 %  |  0.29  |
| *SPY buy & hold*         | 10.51 % | 19.7 % | 0.61 | −55.2 %  |  0.19  |
| *Trend-Parity SMA150 x1.2* | **11.50 %** | 11.5 % | **1.01** | **−16.3 %** | **0.71** |

**None of the Davey variants beat the Trend-Parity baseline**, or even
catch SPY buy & hold, on this window.

Why the original Davey 5-ETF portfolio underperforms:

1. **USO** is structurally toxic (−6.9 % CAGR over 2007-2026, futures
   contango drag, −91.8 % max DD).  Any long-only rules-based system
   that allocates capital to USO forfeits a meaningful portion of
   expected return.
2. **EEM** only earns 2.5 % CAGR with a −60.5 % DD over the same window.
3. **XLF** is hit hard in 2008-09 (−42.9 % DD) — the breakout rule does
   not exit fast enough during the GFC, and re-enters during dead-cat
   bounces.
4. The **20 % fixed-allocation rule** means gross exposure is ≤ 100 %
   only when all 5 ETFs are simultaneously long; in practice the
   portfolio is typically ~40-60 % exposed and earns a large fraction of
   its time parked in BIL.

## Sensitivity of (x1, x2) on QQQ/IEF/GLD (full 1999-2026 history)

Instead of blaming the 5-ETF universe, I asked whether Davey's
**signal** itself is useful when applied to Trend-Parity's own assets.
I ran a 7×7 grid of `(x1, x2)` combinations, no start-date filter,
inverse-vol weighting (so the gate is the only variable):

| (x1, x2)   | CAGR   | MaxDD    | Sharpe | Calmar |
| ---------- | -----: | -------: | -----: | -----: |
| **(4, 5)** (*original*) | 6.45 % | −21.0 % | 0.76 | 0.31 |
| (6, 6)     | 6.21 % | −21.7 % | 0.71   | 0.29  |
| (6, 8)     | 7.52 % | −19.9 % | 0.86   | 0.38  |
| **(8, 3)** | 8.59 % | **−14.6 %** | 0.93 | **0.59** |
| **(8, 8)** | 8.61 % | **−14.6 %** | **0.98** | **0.59** |
| (8, 12)    | 8.45 % | −17.6 % | 1.05   | 0.48  |
| (10, 3)    | 7.75 % | −19.3 % | 0.88   | 0.40  |
| (12, 12)   | 7.20 % | −26.2 % | 0.83   | 0.28  |
| *SMA-150 reference* | **10.37 %** | −17.3 % | 0.96 | **0.60** |

The grid tells a clean story:

* The exact `(4, 5)` pair Davey shipped in the paper is **not** the best
  setting on either the 5-ETF universe or QQQ/IEF/GLD.
* The best monthly-breakout setting on my universe is **`(x1, x2) = (8, 8)`**
  — essentially an 8-month breakout — and even that ties the SMA-150
  gate on Calmar (0.59 vs 0.60).
* (8, 8) trades **lower CAGR for lower drawdown**: 8.61 % @ −14.6 %,
  whereas SMA-150 is 10.37 % @ −17.3 %.
* This is the **smallest MaxDD** of any long-only configuration I have
  tested across all 400+ backtests in this project — but still ≥ 4.6 %
  above the 10 % hard target.

Leveraging Davey 8/8 to match QQQ's CAGR:

|                      | CAGR    | MaxDD   | Sharpe | Calmar |
| -------------------- | ------: | ------: | -----: | -----: |
| Davey 8/8 × 1.0      |  8.61 % | −14.6 % | 0.98   | 0.59   |
| Davey 8/8 × 1.2      |  9.89 % | −17.5 % | 0.95   | 0.56   |
| Davey 8/8 × 1.4 (est)| ~11.1 % | ~−20 %  |        |        |

Even at 1.4× the strategy falls short of the Trend-Parity 1.2×
(11.98 % / −20.5 %) and sits on the same efficient frontier.

## Blending Trend-Parity with the Davey portfolios

50/50 blend between Trend-Parity (SMA-150 x1.2) and the best Davey
variants, on 2007-01 → 2026-04:

| Blend                    | CAGR   | MaxDD    | Sharpe | Calmar |
| ------------------------ | -----: | -------: | -----: | -----: |
| **100 % Trend-Parity**   | **11.50 %** | **−16.3 %** | **1.01** | **0.71** |
| 75 % TP + 25 % Davey V5  | 10.15 % | −17.1 % | 0.98 | 0.59 |
| 50 % TP + 50 % Davey V3  |  9.43 % | −19.8 % | 0.90 | 0.48 |
| 50 % TP + 50 % Davey V5  |  8.73 % | −18.8 % | 0.89 | 0.46 |
| 50 % TP + 50 % Davey V5c |  8.82 % | −18.8 % | 0.88 | 0.47 |
| 25 % TP + 75 % Davey V5  |  7.26 % | −22.5 % | 0.74 | 0.32 |
| 100 % Davey V5           |  5.73 % | −26.4 % | 0.56 | 0.22 |

**Adding Davey dilutes the Pareto frontier monotonically.**  Every extra
unit of Davey exposure pushes CAGR down faster than it pulls MaxDD up,
so the optimal blend is **0 %** Davey.

## Combined AND / OR gates (QQQ/IEF/GLD, 1999-2026)

What if we filter assets through **both** the SMA-150 and the Davey
gate simultaneously?

| Gate                       | CAGR   | MaxDD    | Sharpe | Calmar |
| -------------------------- | -----: | -------: | -----: | -----: |
| SMA150 **only**            | 10.37 % | −17.3 % | 0.96 | 0.60 |
| Davey 8/8 **only**         |  8.61 % | −14.6 % | 0.98 | 0.59 |
| SMA150 **AND** Davey 8/8   |  9.20 % | **−36.5 %** | 0.74 | 0.25 |
| SMA150 **OR**  Davey 8/8   |  8.41 % | −17.7 % | 1.05 | 0.48 |

The **AND** gate catastrophically **increases** drawdown to −36.5 %
because both signals have to be triggered to exit, which multiplies
the signal lag during 2008 and 2022.  The **OR** gate is effectively a
trivial combination and adds nothing.

## Conclusion

1. **Kevin Davey's (4, 5) monthly breakout does not improve on
   Trend-Parity** — neither as a stand-alone portfolio strategy, nor as
   a filter substitution, nor as an ensemble component.

2. The one positive finding is that an **optimised (8, 8) version of
   the same breakout rule on QQQ/IEF/GLD** produces the **lowest
   drawdown I was able to build into a beat-the-market strategy
   (−14.62 %)**.  Applied levered it still underperforms the SMA-150
   version of Trend-Parity on CAGR.

3. On the original 5-ETF universe the Davey algorithm is structurally
   handicapped by **USO** and **EEM**, whose 2007-2026 returns are too
   poor for any timing overlay to save.  Davey's published results
   presumably come from an earlier window (pre-2014, before oil's
   structural decline and before EEM's lost decade).

4. **The shipped strategy in `strategy.py` is unchanged**: Trend-Parity
   with SMA-150 / 40-day inv-vol / 1.2× leverage remains the Pareto
   optimum on the ETF-only frontier.  The new exploration only
   strengthens that conclusion and adds 4 more scripts' worth of
   evidence for the claim that the ≤ 10 % MaxDD target is infeasible.

## Files added in this round

| File                  | Purpose                                       |
| --------------------- | --------------------------------------------- |
| `davey_strategy.py`   | Literal translation of Davey's EL into Python + 5-ETF portfolio |
| `davey_variants.py`   | V1-V5c allocation variants + TP blends        |
| `davey_on_tp.py`      | Head-to-head Davey vs SMA-150 on QQQ/IEF/GLD  |
| `davey_final.py`      | Full-history grid search of (x1, x2) + AND/OR gates |
| `davey_addendum.md`   | This document                                 |
