"""
Backtest de la strategie "Little Rizzie" (Marci Silfrain) sur NQ=F.

Strategie (Long uniquement) :
  - Actif        : NQ=F (E-mini Nasdaq 100 Future), donnees journalieres.
  - Periode      : 2018-01-01 -> aujourd'hui.
  - Indicateurs  : Bandes de Bollinger (20, 2.0), Swing Highs / Swing Lows
                   detectes sur une fenetre glissante de 5 jours (pivots).
  - Entree (Long): La veille, le Low a touche/franchi a la baisse la bande
                   de Bollinger inferieure ET aujourd'hui le Close casse a la
                   hausse le dernier Swing High valide (Break of Structure).
                   -> achat de 1 contrat a la cloture.
  - Sortie       : Trailing stop structurel. On clot la position si le Close
                   journalier passe sous le dernier Swing Low valide.
  - Position     : 1 contrat E-mini NQ. 1 point = 20 $. Capital initial 100k$.

Gestion du lookahead bias :
  Un pivot (swing) sur fenetre de 5 jours necessite k=2 bougies a sa droite
  pour etre confirme. Le niveau d'un swing detecte a la barre i n'est donc
  "connu" qu'a partir de la barre i+k. On decale les niveaux de swing valides
  de k barres avant de les utiliser comme references de trading.
"""

import time
import datetime as dt

import numpy as np
import pandas as pd
import requests

# ----------------------------- Parametres ---------------------------------
TICKER          = "NQ=F"
START           = "2018-01-01"
END             = None              # None => jusqu'a aujourd'hui
BB_PERIOD       = 20
BB_STD          = 2.0
SWING_WINDOW    = 5                 # fenetre glissante totale (pivot)
POINT_VALUE     = 20.0             # $ par point NQ
INITIAL_CAPITAL = 100_000.0
CONTRACTS       = 1

# Pour une fenetre de 5 jours, le pivot est la bougie centrale : k bougies
# de chaque cote. k = (5 - 1) / 2 = 2  -> 2 barres de confirmation a droite.
K = (SWING_WINDOW - 1) // 2


def load_data():
    """
    Telecharge les donnees journalieres NQ=F via l'API chart de Yahoo Finance
    (requests). On evite yfinance/curl_cffi qui echoue en TLS a travers le
    proxy d'egress de l'environnement. Retry avec backoff exponentiel.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}"
    p1 = int(dt.datetime(2018, 1, 1).timestamp())
    p2 = int(time.time()) if END is None else int(
        dt.datetime.fromisoformat(END).timestamp())
    params = {"period1": p1, "period2": p2, "interval": "1d"}
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36")
    }

    last_err = None
    for attempt in range(5):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                res = r.json()["chart"]["result"][0]
                ts = res["timestamp"]
                q = res["indicators"]["quote"][0]
                df = pd.DataFrame({
                    "Open":   q["open"],
                    "High":   q["high"],
                    "Low":    q["low"],
                    "Close":  q["close"],
                    "Volume": q["volume"],
                }, index=pd.to_datetime(ts, unit="s"))
                df.index = df.index.normalize()
                df = df.dropna(subset=["Open", "High", "Low", "Close"])
                # Filtre strict de la periode demandee.
                df = df[df.index >= pd.Timestamp(START)]
                return df
            last_err = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        wait = 2 ** (attempt + 1)
        print(f"  echec ({last_err}), nouvelle tentative dans {wait}s...")
        time.sleep(wait)

    raise RuntimeError(f"Impossible de telecharger {TICKER}: {last_err}")


def add_bollinger(df):
    mid = df["Close"].rolling(BB_PERIOD).mean()
    sd  = df["Close"].rolling(BB_PERIOD).std(ddof=0)
    df["BB_mid"]   = mid
    df["BB_upper"] = mid + BB_STD * sd
    df["BB_lower"] = mid - BB_STD * sd
    return df


def add_swings(df):
    """
    Detecte les pivots (swing high/low) sur une fenetre centree de 5 barres
    puis propage le DERNIER niveau valide, decale de K barres pour eviter
    tout lookahead bias (un pivot a la barre i est connu a la barre i+K).
    """
    high = df["High"].to_numpy()
    low  = df["Low"].to_numpy()
    n    = len(df)

    is_swing_high = np.zeros(n, dtype=bool)
    is_swing_low  = np.zeros(n, dtype=bool)

    # La bougie centrale i est un swing high si son High est strictement le
    # plus haut de la fenetre [i-K, i+K] (idem, plus bas, pour swing low).
    for i in range(K, n - K):
        win_h = high[i - K:i + K + 1]
        win_l = low[i - K:i + K + 1]
        if high[i] == win_h.max() and (win_h == high[i]).sum() == 1:
            is_swing_high[i] = True
        if low[i] == win_l.min() and (win_l == low[i]).sum() == 1:
            is_swing_low[i] = True

    # Niveau du pivot le jour de sa formation (NaN ailleurs).
    swing_high_level = np.where(is_swing_high, high, np.nan)
    swing_low_level  = np.where(is_swing_low,  low,  np.nan)

    sh = pd.Series(swing_high_level, index=df.index)
    sl = pd.Series(swing_low_level,  index=df.index)

    # Decalage de K barres : le niveau n'est connu qu'apres confirmation,
    # puis on propage (ffill) le dernier swing valide connu.
    df["last_swing_high"] = sh.shift(K).ffill()
    df["last_swing_low"]  = sl.shift(K).ffill()
    return df


def run_backtest(df):
    equity_curve = []
    trades = []

    cash        = INITIAL_CAPITAL
    in_position = False
    entry_price = np.nan
    entry_date  = None

    closes = df["Close"]
    lows   = df["Low"]

    for i in range(1, len(df)):
        date  = df.index[i]
        close = float(closes.iloc[i])

        prev_low      = float(lows.iloc[i - 1])
        prev_bb_lower = float(df["BB_lower"].iloc[i - 1])
        swing_high    = df["last_swing_high"].iloc[i]
        swing_low     = df["last_swing_low"].iloc[i]

        # ----- Gestion de la sortie (position ouverte) -----
        if in_position:
            if not np.isnan(swing_low) and close < float(swing_low):
                pnl = (close - entry_price) * POINT_VALUE * CONTRACTS
                cash += pnl
                trades.append({
                    "entry_date":  entry_date,
                    "exit_date":   date,
                    "entry_price": entry_price,
                    "exit_price":  close,
                    "points":      close - entry_price,
                    "pnl":         pnl,
                })
                in_position = False
                entry_price = np.nan
                entry_date  = None

        # ----- Gestion de l'entree (pas de position) -----
        if not in_position:
            cond_bb    = (not np.isnan(prev_bb_lower)) and (prev_low <= prev_bb_lower)
            cond_bos   = (not np.isnan(swing_high)) and (close > float(swing_high))
            if cond_bb and cond_bos:
                in_position = True
                entry_price = close
                entry_date  = date

        # ----- Equity mark-to-market -----
        if in_position:
            unrealized = (close - entry_price) * POINT_VALUE * CONTRACTS
            equity_curve.append((date, cash + unrealized))
        else:
            equity_curve.append((date, cash))

    # Cloture forcee de la derniere position au dernier close (mark-to-market)
    if in_position:
        last_close = float(closes.iloc[-1])
        pnl = (last_close - entry_price) * POINT_VALUE * CONTRACTS
        cash += pnl
        trades.append({
            "entry_date":  entry_date,
            "exit_date":   df.index[-1],
            "entry_price": entry_price,
            "exit_price":  last_close,
            "points":      last_close - entry_price,
            "pnl":         pnl,
            "note":        "cloture forcee fin de backtest",
        })

    eq = pd.DataFrame(equity_curve, columns=["date", "equity"]).set_index("date")
    return cash, pd.DataFrame(trades), eq


def summarize(final_cash, trades, eq):
    net_profit = final_cash - INITIAL_CAPITAL
    n_trades   = len(trades)

    if n_trades:
        wins      = trades[trades["pnl"] > 0]
        win_rate  = 100.0 * len(wins) / n_trades
        avg_win   = wins["pnl"].mean() if len(wins) else 0.0
        losses    = trades[trades["pnl"] <= 0]
        avg_loss  = losses["pnl"].mean() if len(losses) else 0.0
        gross_win = wins["pnl"].sum()
        gross_los = losses["pnl"].sum()
        pf        = (gross_win / abs(gross_los)) if gross_los != 0 else float("inf")
    else:
        win_rate = avg_win = avg_loss = pf = 0.0

    # Max drawdown sur la courbe d'equity
    if len(eq):
        running_max = eq["equity"].cummax()
        drawdown    = eq["equity"] - running_max
        max_dd      = drawdown.min()
        dd_pct      = (drawdown / running_max).min() * 100.0
    else:
        max_dd = dd_pct = 0.0

    print("=" * 60)
    print("  BACKTEST 'LITTLE RIZZIE'  -  NQ=F (Daily)")
    print("=" * 60)
    print(f"  Periode               : {START} -> {'aujourd hui' if END is None else END}")
    print(f"  Capital initial       : {INITIAL_CAPITAL:,.2f} $")
    print(f"  Capital final         : {final_cash:,.2f} $")
    print(f"  Profit Net            : {net_profit:,.2f} $  ({net_profit/INITIAL_CAPITAL*100:.2f} %)")
    print(f"  Nombre total de trades: {n_trades}")
    print(f"  Win Rate              : {win_rate:.2f} %")
    print(f"  Gain moyen / trade gagnant : {avg_win:,.2f} $")
    print(f"  Perte moyenne / trade perdant : {avg_loss:,.2f} $")
    print(f"  Profit Factor         : {pf:.2f}")
    print(f"  Drawdown Maximum      : {max_dd:,.2f} $  ({dd_pct:.2f} %)")
    print("=" * 60)

    if n_trades:
        print("\n  Detail des trades :")
        show = trades.copy()
        show["entry_date"] = pd.to_datetime(show["entry_date"]).dt.date
        show["exit_date"]  = pd.to_datetime(show["exit_date"]).dt.date
        for col in ("entry_price", "exit_price", "points", "pnl"):
            show[col] = show[col].round(2)
        with pd.option_context("display.max_rows", None, "display.width", 120):
            print(show.to_string(index=False))


def main():
    print(f"Telechargement des donnees {TICKER} ...")
    df = load_data()
    print(f"  {len(df)} bougies journalieres recuperees "
          f"({df.index[0].date()} -> {df.index[-1].date()}).")
    df = add_bollinger(df)
    df = add_swings(df)
    final_cash, trades, eq = run_backtest(df)
    summarize(final_cash, trades, eq)


if __name__ == "__main__":
    main()
