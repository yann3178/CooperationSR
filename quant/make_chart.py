"""Generate the backtest visualisation PNG."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from strategy import run_backtest_strategy, RISKY, CASH

OUT = os.path.join(os.path.dirname(__file__), "backtest_chart.png")


def main():
    df = run_backtest_strategy()
    m = df.attrs["metrics"]

    fig, axes = plt.subplots(
        3, 1, figsize=(12, 10.5),
        gridspec_kw={"height_ratios": [2.3, 1.2, 1.2]},
        sharex=True,
    )

    # --- 1) Equity curve (log) ---
    ax = axes[0]
    ax.semilogy(df.index, df["equity"], label="Trend-Parity",
                color="#1f77b4", lw=2.0)
    ax.semilogy(df.index, df["qqq"], label="QQQ buy & hold",
                color="#d62728", lw=1.4, alpha=0.85)
    ax.set_title(
        f"Trend-Parity vs QQQ (1999-2026) — "
        f"CAGR {m.cagr*100:.2f}% / MaxDD {m.max_dd*100:.2f}% / "
        f"Sharpe {m.sharpe:.2f}  (QQQ: 10.37% / -82.96% / 0.50)"
    )
    ax.set_ylabel("Equity (log, starts at 1)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="upper left")

    # --- 2) Drawdown ---
    ax = axes[1]
    ax.fill_between(df.index, df["drawdown"] * 100, 0,
                    color="#1f77b4", alpha=0.65, label="Trend-Parity DD")
    ax.plot(df.index, df["qqq_dd"] * 100, color="#d62728",
            lw=1.1, alpha=0.7, label="QQQ DD")
    ax.axhline(-10, color="black", linestyle="--", lw=0.8,
               label="-10% target")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=9)

    # --- 3) Stacked allocation ---
    ax = axes[2]
    cols_w = [f"w_{c}" for c in RISKY] + [f"w_{CASH}"]
    alloc = df[cols_w].copy()
    alloc.columns = RISKY + [CASH]
    # Clip BIL to zero for the stacked chart to avoid confusing the viewer;
    # leverage (negative BIL) is still shown via the sum above 1.0.
    pos = alloc.clip(lower=0)
    neg = (-alloc.clip(upper=0)).sum(axis=1)  # leverage footprint
    colors = {"QQQ": "#1f77b4", "IEF": "#2ca02c",
              "GLD": "#ff7f0e", "BIL": "#7f7f7f"}
    ax.stackplot(df.index,
                 [pos[c].values for c in RISKY + [CASH]],
                 labels=RISKY + [CASH],
                 colors=[colors[c] for c in RISKY + [CASH]])
    ax.plot(df.index, pos.sum(axis=1).values,
            color="k", lw=0.8, alpha=0.5)
    ax.set_ylabel("Allocation")
    ax.set_xlabel("Date")
    ax.set_ylim(0, 1.35)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9, ncols=4)
    ax.xaxis.set_major_locator(mdates.YearLocator(3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.tight_layout()
    fig.savefig(OUT, dpi=140)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
