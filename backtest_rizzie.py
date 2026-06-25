"""
Backtest de la strategie "Little Rizzie" (Marci Silfrain) sur NQ=F.

Strategie (Long uniquement) :
  - Actif        : NQ=F (E-mini Nasdaq 100 Future), donnees journalieres.
  - Periode      : 2018-01-01 -> aujourd'hui.
  - Indicateurs  : Bandes de Bollinger (20, 2.0), Swing Highs / Swing Lows
                   detectes sur une fenetre glissante de 5 jours (pivots).
  - Entree (Long): Depuis que la structure est baissiere (un Close est passe
                   sous le dernier Swing Low valide), le prix a cloture sous la
                   bande de Bollinger inferieure (crossover en cloture) ET
                   aujourd'hui le Close casse a la hausse le dernier Swing High
                   valide (Break of Structure haussier) ET l'ADX(14) > 20
                   (filtre de force de tendance) ET (optionnel) la Confluence
                   Fibonacci : la cible baissiere Rizzie (SwingLow - (SwingHigh
                   - SwingLow)) tombe pres d'un niveau de Fib (38.2/50/61.8 %)
                   du dernier macro bull run, a FIB_TOLERANCE_PCT % pres.
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

import sys
import time
import datetime as dt

import numpy as np
import pandas as pd
import requests

# ----------------------------- Parametres ---------------------------------
START           = "2018-01-01"
END             = None              # None => jusqu'a aujourd'hui
BB_PERIOD       = 20
BB_STD          = 2.0
SWING_WINDOW    = 5                 # fenetre glissante totale (pivot)
ADX_PERIOD      = 14                # periode de l'ADX
ADX_THRESHOLD   = 20.0             # filtre d'entree : ADX doit etre > ce seuil
INITIAL_CAPITAL = 100_000.0
CONTRACTS       = 1

# --- Filtre de Confluence Fibonacci (methode Marci Silfrain) ---------------
# Active une condition d'entree supplementaire : la cible baissiere theorique
# du motif Rizzie doit tomber en confluence avec un niveau de Fibonacci majeur
# du dernier macro bull run.
USE_FIB_FILTER    = True
FIB_TOLERANCE_PCT = 1.5            # largeur de la bande autour du niveau Fib (%)
MACRO_LOOKBACK    = 252            # fenetre du macro bull run (en barres)
FIB_LEVELS        = (0.382, 0.5, 0.618)

# Instruments backtestes. point = valeur monetaire d'un point d'indice par
# contrat. Le DAX n'a pas de future propre sur Yahoo : on utilise l'indice
# ^GDAXI comme proxy du future FDAX (25 EUR / point).
INSTRUMENTS = {
    "NQ":  {"ticker": "NQ=F",   "point": 20.0, "ccy": "USD",
            "name": "Nasdaq 100 future (NQ=F)"},
    "ES":  {"ticker": "ES=F",   "point": 50.0, "ccy": "USD",
            "name": "S&P 500 future (ES=F)"},
    "YM":  {"ticker": "YM=F",   "point": 5.0,  "ccy": "USD",
            "name": "Dow Jones future (YM=F)"},
    "DAX": {"ticker": "^GDAXI", "point": 25.0, "ccy": "EUR",
            "name": "DAX future (proxy ^GDAXI)"},
    "CAC": {"ticker": "^FCHI",  "point": 10.0, "ccy": "EUR",
            "name": "CAC 40 future (proxy ^FCHI)"},
    "IBEX": {"ticker": "^IBEX", "point": 10.0, "ccy": "EUR",
            "name": "IBEX 35 future (proxy ^IBEX)"},
    # Bitcoin spot : 1 point = 1 USD pour 1 BTC detenu (~notionnel 1x).
    "BTC": {"ticker": "BTC-USD", "point": 1.0, "ccy": "USD",
            "name": "Bitcoin (BTC-USD spot, 1 BTC)"},
}

# Pour une fenetre de 5 jours, le pivot est la bougie centrale : k bougies
# de chaque cote. k = (5 - 1) / 2 = 2  -> 2 barres de confirmation a droite.
K = (SWING_WINDOW - 1) // 2


def _yahoo_chart(params, ticker):
    """Appel brut a l'API chart de Yahoo avec retry / backoff exponentiel."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
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
                return df.dropna(subset=["Open", "High", "Low", "Close"])
            last_err = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        wait = 2 ** (attempt + 1)
        print(f"  echec ({last_err}), nouvelle tentative dans {wait}s...")
        time.sleep(wait)
    raise RuntimeError(f"Impossible de telecharger {ticker}: {last_err}")


def load_data(ticker, interval="1d"):
    """
    Telecharge les donnees d'un instrument via l'API chart de Yahoo Finance
    (requests : on evite yfinance/curl_cffi qui echoue en TLS a travers le
    proxy d'egress).

    Intervalles geres :
      "1d"  : journalier, historique complet depuis 2018-01-01.
      "1wk" : hebdomadaire, historique complet depuis 2018-01-01.
      "4h"  : reconstruit par resampling du 1H (Yahoo n'a pas de 4H natif).
              Note : l'intraday Yahoo est limite a ~730 jours d'historique,
              donc le backtest 4H ne couvre que les ~2 dernieres annees.
    """
    if interval in ("1d", "1wk"):
        p1 = int(dt.datetime(2018, 1, 1).timestamp())
        p2 = int(time.time()) if END is None else int(
            dt.datetime.fromisoformat(END).timestamp())
        df = _yahoo_chart(
            {"period1": p1, "period2": p2, "interval": interval}, ticker)
        if interval == "1d":
            df.index = df.index.normalize()
        df = df[df.index >= pd.Timestamp(START)]
        return df

    if interval == "4h":
        # Yahoo ne fournit pas de 4H : on prend le 1H max dispo et on agrege.
        hourly = _yahoo_chart({"range": "730d", "interval": "1h"}, ticker)
        agg = {"Open": "first", "High": "max", "Low": "min",
               "Close": "last", "Volume": "sum"}
        df = hourly.resample("4h").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])
        return df

    raise ValueError(f"Intervalle non supporte : {interval}")


def add_bollinger(df):
    mid = df["Close"].rolling(BB_PERIOD).mean()
    sd  = df["Close"].rolling(BB_PERIOD).std(ddof=0)
    df["BB_mid"]   = mid
    df["BB_upper"] = mid + BB_STD * sd
    df["BB_lower"] = mid - BB_STD * sd
    return df


def add_adx(df, period=14):
    """
    Calcule l'ADX (Average Directional Index) selon la methode de Wilder.
    L'ADX a la barre i n'utilise que des donnees jusqu'a i incluse : comme
    l'entree se fait au close du jour i (avec le close de i), aucun lookahead.
    """
    high  = df["High"]
    low   = df["Low"]
    close = df["Close"]

    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Lissage de Wilder (equivaut a un EMA d'alpha = 1/period).
    alpha = 1.0 / period
    atr      = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di  = 100.0 * pd.Series(plus_dm,  index=df.index).ewm(alpha=alpha, adjust=False).mean() / atr
    minus_di = 100.0 * pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean() / atr

    dx  = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    df["ADX"] = adx
    return df


def add_swings(df, window=SWING_WINDOW):
    """
    Detecte les pivots (swing high/low) sur une fenetre centree de `window`
    barres puis propage le DERNIER niveau valide, decale de k barres pour
    eviter tout lookahead bias (un pivot a la barre i est connu a la barre i+k).
    """
    k = (window - 1) // 2
    high = df["High"].to_numpy()
    low  = df["Low"].to_numpy()
    n    = len(df)

    is_swing_high = np.zeros(n, dtype=bool)
    is_swing_low  = np.zeros(n, dtype=bool)

    # La bougie centrale i est un swing high si son High est strictement le
    # plus haut de la fenetre [i-k, i+k] (idem, plus bas, pour swing low).
    for i in range(k, n - k):
        win_h = high[i - k:i + k + 1]
        win_l = low[i - k:i + k + 1]
        if high[i] == win_h.max() and (win_h == high[i]).sum() == 1:
            is_swing_high[i] = True
        if low[i] == win_l.min() and (win_l == low[i]).sum() == 1:
            is_swing_low[i] = True

    # Niveau du pivot le jour de sa formation (NaN ailleurs).
    swing_high_level = np.where(is_swing_high, high, np.nan)
    swing_low_level  = np.where(is_swing_low,  low,  np.nan)

    sh = pd.Series(swing_high_level, index=df.index)
    sl = pd.Series(swing_low_level,  index=df.index)

    # Decalage de k barres : le niveau n'est connu qu'apres confirmation,
    # puis on propage (ffill) le dernier swing valide connu.
    df["last_swing_high"] = sh.shift(k).ffill()
    df["last_swing_low"]  = sl.shift(k).ffill()
    return df


def add_fib(df, lookback=MACRO_LOOKBACK):
    """
    Filtre de Confluence Fibonacci (Marci Silfrain).

    Pour chaque barre i, on regarde la fenetre macro [i-lookback+1, i] (passe
    uniquement -> pas de lookahead) :
      - Macro_Low / Macro_High = plus bas / plus haut absolus de la fenetre.
      - Dynamique haussiere validee si le plus haut survient APRES le plus bas
        (impulsion macro a la hausse).
      - Niveaux de retracement de Fib (38.2 / 50 / 61.8 %) de cette impulsion :
            niveau = Macro_High - r * (Macro_High - Macro_Low).
    Les niveaux ne dependent pas de la tolerance : ils sont calcules une fois,
    la confluence avec la cible Rizzie est testee plus tard dans le backtest.
    """
    high = df["High"].to_numpy()
    low  = df["Low"].to_numpy()
    n    = len(df)

    macro_bull = np.zeros(n, dtype=bool)
    fib = {r: np.full(n, np.nan) for r in FIB_LEVELS}

    for i in range(lookback - 1, n):
        w_lo = low[i - lookback + 1:i + 1]
        w_hi = high[i - lookback + 1:i + 1]
        lo, hi = w_lo.min(), w_hi.max()
        pos_lo = int(w_lo.argmin())
        pos_hi = int(w_hi.argmax())
        # Impulsion haussiere : creux d'abord, sommet ensuite, et amplitude > 0.
        if pos_hi > pos_lo and hi > lo:
            macro_bull[i] = True
            rng = hi - lo
            for r in FIB_LEVELS:
                fib[r][i] = hi - r * rng

    df["macro_bull"] = macro_bull
    for r in FIB_LEVELS:
        df[f"fib_{int(r*1000)}"] = fib[r]
    return df


def run_backtest(df, point_value, use_fib=None, fib_tol=None):
    use_fib = USE_FIB_FILTER if use_fib is None else use_fib
    fib_tol = FIB_TOLERANCE_PCT if fib_tol is None else fib_tol
    fib_cols = [f"fib_{int(r*1000)}" for r in FIB_LEVELS] if use_fib else []

    equity_curve = []
    trades = []

    cash        = INITIAL_CAPITAL
    in_position = False
    entry_price = np.nan
    entry_date  = None

    # Etat de structure de marche pour la condition d'entree :
    #   structure == "bear" apres une cassure baissiere (close < swing low).
    #   bb_breach == True si, DEPUIS le debut de la phase baissiere en cours,
    #   le prix a cloture sous la bande de Bollinger inferieure.
    structure = "bull"
    bb_breach = False

    closes = df["Close"]
    lows   = df["Low"]

    for i in range(1, len(df)):
        date  = df.index[i]
        close = float(closes.iloc[i])

        bb_lower   = df["BB_lower"].iloc[i]
        swing_high = df["last_swing_high"].iloc[i]
        swing_low  = df["last_swing_low"].iloc[i]

        # ----- Gestion de la sortie (position ouverte) -----
        if in_position:
            if not np.isnan(swing_low) and close < float(swing_low):
                pnl = (close - entry_price) * point_value * CONTRACTS
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
                # La cassure baissiere du swing low fait basculer la structure
                # en mode baissier et reinitialise le suivi de la bande.
                structure = "bear"
                bb_breach = False

        # ----- Mise a jour de la structure / suivi de la bande basse -----
        if not in_position:
            # Cassure baissiere de structure : close sous le dernier swing low.
            if not np.isnan(swing_low) and close < float(swing_low):
                if structure != "bear":
                    structure = "bear"
                    bb_breach = False
            # Pendant la phase baissiere, memorise un close sous la bande basse.
            if structure == "bear" and not np.isnan(bb_lower) \
                    and close <= float(bb_lower):
                bb_breach = True

        # ----- Gestion de l'entree (pas de position) -----
        if not in_position:
            # Entree long : on est en structure baissiere, le prix a cloture
            # sous la bande inferieure depuis le debut de cette phase, et le
            # close du jour casse a la hausse le dernier swing high (BoS).
            cond_struct = (structure == "bear") and bb_breach
            cond_bos    = (not np.isnan(swing_high)) and (close > float(swing_high))
            adx_val     = df["ADX"].iloc[i]
            cond_adx    = (not np.isnan(adx_val)) and (adx_val > ADX_THRESHOLD)

            # ----- Filtre de Confluence Fibonacci (optionnel) -----
            cond_fib = True
            if use_fib:
                cond_fib = False
                if df["macro_bull"].iloc[i] and not np.isnan(swing_high) \
                        and not np.isnan(swing_low):
                    # Cible Rizzie : D = SwingHigh - SwingLow, reportee sous
                    # le SwingLow -> target = SwingLow - D.
                    dist   = float(swing_high) - float(swing_low)
                    target = float(swing_low) - dist
                    if target > 0:
                        for col in fib_cols:
                            lvl = df[col].iloc[i]
                            if not np.isnan(lvl) and lvl > 0 and \
                                    abs(target - lvl) / lvl <= fib_tol / 100.0:
                                cond_fib = True
                                break

            if cond_struct and cond_bos and cond_adx and cond_fib:
                in_position = True
                entry_price = close
                entry_date  = date
                # Le BoS haussier fait basculer la structure en mode haussier.
                structure = "bull"
                bb_breach = False

        # ----- Equity mark-to-market -----
        if in_position:
            unrealized = (close - entry_price) * point_value * CONTRACTS
            equity_curve.append((date, cash + unrealized))
        else:
            equity_curve.append((date, cash))

    # Cloture forcee de la derniere position au dernier close (mark-to-market)
    if in_position:
        last_close = float(closes.iloc[-1])
        pnl = (last_close - entry_price) * point_value * CONTRACTS
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


def compute_stats(final_cash, trades, eq):
    """Renvoie un dict de metriques de performance (reutilisable)."""
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

    if len(eq):
        running_max = eq["equity"].cummax()
        drawdown    = eq["equity"] - running_max
        max_dd      = drawdown.min()
        dd_pct      = (drawdown / running_max).min() * 100.0
    else:
        max_dd = dd_pct = 0.0

    return {
        "final_cash": final_cash, "net_profit": net_profit,
        "n_trades": n_trades, "win_rate": win_rate, "pf": pf,
        "avg_win": avg_win, "avg_loss": avg_loss,
        "max_dd": max_dd, "dd_pct": dd_pct,
    }


def summarize(final_cash, trades, eq, label="Daily", period_txt=None,
              inst_name="Nasdaq 100 future (NQ=F)", ccy="USD"):
    s = compute_stats(final_cash, trades, eq)
    net_profit = s["net_profit"]; n_trades = s["n_trades"]
    win_rate = s["win_rate"]; avg_win = s["avg_win"]; avg_loss = s["avg_loss"]
    pf = s["pf"]; max_dd = s["max_dd"]; dd_pct = s["dd_pct"]

    print("=" * 64)
    print(f"  BACKTEST 'LITTLE RIZZIE'  -  {inst_name} ({label})")
    print("=" * 64)
    print(f"  Periode               : {period_txt or START + ' -> aujourd hui'}")
    print(f"  Capital initial       : {INITIAL_CAPITAL:,.2f} {ccy}")
    print(f"  Capital final         : {final_cash:,.2f} {ccy}")
    print(f"  Profit Net            : {net_profit:,.2f} {ccy}  ({net_profit/INITIAL_CAPITAL*100:.2f} %)")
    print(f"  Nombre total de trades: {n_trades}")
    print(f"  Win Rate              : {win_rate:.2f} %")
    print(f"  Gain moyen / trade gagnant : {avg_win:,.2f} {ccy}")
    print(f"  Perte moyenne / trade perdant : {avg_loss:,.2f} {ccy}")
    print(f"  Profit Factor         : {pf:.2f}")
    print(f"  Drawdown Maximum      : {max_dd:,.2f} {ccy}  ({dd_pct:.2f} %)")
    print("=" * 64)

    if n_trades:
        print("\n  Detail des trades :")
        show = trades.copy()
        if label == "4H":
            show["entry_date"] = pd.to_datetime(show["entry_date"])
            show["exit_date"]  = pd.to_datetime(show["exit_date"])
        else:
            show["entry_date"] = pd.to_datetime(show["entry_date"]).dt.date
            show["exit_date"]  = pd.to_datetime(show["exit_date"]).dt.date
        for col in ("entry_price", "exit_price", "points", "pnl"):
            show[col] = show[col].round(2)
        with pd.option_context("display.max_rows", None, "display.width", 120):
            print(show.to_string(index=False))


def prepare(inst_key, interval):
    """Charge les donnees et calcule tous les indicateurs une seule fois."""
    inst = INSTRUMENTS[inst_key]
    print(f"\nTelechargement des donnees {inst['ticker']} "
          f"[{inst['name']}] ({interval}) ...")
    df = load_data(inst["ticker"], interval)
    p0, p1 = df.index[0], df.index[-1]
    print(f"  {len(df)} bougies recuperees ({p0} -> {p1}).")
    df = add_bollinger(df)
    df = add_adx(df, ADX_PERIOD)
    df = add_swings(df)
    df = add_fib(df)
    return df, inst, (p0, p1)


def run_one(inst_key, interval, label):
    df, inst, (p0, p1) = prepare(inst_key, interval)
    final_cash, trades, eq = run_backtest(df, inst["point"])
    fib_txt = (f"  (Filtre Fib : ON, tolerance {FIB_TOLERANCE_PCT}%)"
               if USE_FIB_FILTER else "  (Filtre Fib : OFF)")
    print(fib_txt)
    summarize(final_cash, trades, eq, label=label, period_txt=f"{p0} -> {p1}",
              inst_name=inst["name"], ccy=inst["ccy"])


def optimize_fib(inst_key, interval, label):
    """Boucle d'optimisation de FIB_TOLERANCE_PCT (0.5 -> 5.0 %, pas 0.5)."""
    df, inst, (p0, p1) = prepare(inst_key, interval)
    ccy = inst["ccy"]

    # Reference : filtre desactive (baseline).
    fc0, tr0, eq0 = run_backtest(df, inst["point"], use_fib=False)
    base = compute_stats(fc0, tr0, eq0)

    print("\n" + "=" * 78)
    print(f"  OPTIMISATION FILTRE FIBONACCI - {inst['name']} ({label})")
    print(f"  Periode : {p0} -> {p1}")
    print("=" * 78)
    print(f"  {'Tol %':>6} | {'Trades':>6} | {'WinRate':>7} | "
          f"{'PF':>6} | {'Profit Net':>14} | {'DD %':>7}")
    print("  " + "-" * 64)
    print(f"  {'OFF':>6} | {base['n_trades']:>6} | {base['win_rate']:>6.1f}% | "
          f"{base['pf']:>6.2f} | {base['net_profit']:>12,.0f} {ccy[:3]} | "
          f"{base['dd_pct']:>6.1f}%")

    rows = []
    tol = 0.5
    while tol <= 5.0 + 1e-9:
        fc, tr, eq = run_backtest(df, inst["point"], use_fib=True, fib_tol=tol)
        s = compute_stats(fc, tr, eq)
        s["tol"] = tol
        rows.append(s)
        print(f"  {tol:>6.1f} | {s['n_trades']:>6} | {s['win_rate']:>6.1f}% | "
              f"{s['pf']:>6.2f} | {s['net_profit']:>12,.0f} {ccy[:3]} | "
              f"{s['dd_pct']:>6.1f}%")
        tol += 0.5
    print("=" * 78)
    return base, rows


def optimize_swing(inst_key, interval, label, windows=range(3, 22, 2)):
    """
    Optimisation de la fenetre de detection des swings (SWING_WINDOW).
    Filtre Fibonacci DESACTIVE pour isoler l'effet de la fenetre. Les autres
    indicateurs (Bollinger, ADX) sont independants de la fenetre et calcules
    une seule fois ; seuls les swings sont recalcules a chaque iteration.
    """
    df, inst, (p0, p1) = prepare(inst_key, interval)
    ccy = inst["ccy"]

    print("\n" + "=" * 78)
    print(f"  OPTIMISATION FENETRE DE SWING - {inst['name']} ({label})")
    print(f"  Periode : {p0} -> {p1}   |   Filtre Fibonacci : OFF")
    print("=" * 78)
    print(f"  {'Window':>6} | {'k(conf)':>7} | {'Trades':>6} | {'WinRate':>7} | "
          f"{'PF':>6} | {'Profit Net':>14} | {'DD %':>7}")
    print("  " + "-" * 70)

    rows = []
    for w in windows:
        add_swings(df, window=w)            # recalcule last_swing_high/low
        fc, tr, eq = run_backtest(df, inst["point"], use_fib=False)
        s = compute_stats(fc, tr, eq)
        s["window"] = w
        rows.append(s)
        print(f"  {w:>6} | {(w-1)//2:>7} | {s['n_trades']:>6} | "
              f"{s['win_rate']:>6.1f}% | {s['pf']:>6.2f} | "
              f"{s['net_profit']:>12,.0f} {ccy[:3]} | {s['dd_pct']:>6.1f}%")
    print("=" * 78)
    return rows


def main():
    intervals = {"1d": "Daily", "4h": "4H", "1wk": "Weekly"}
    do_opt    = any(a in ("opt", "--opt", "optimize") for a in sys.argv[1:])
    do_swing  = any(a in ("swing", "--swing", "optswing") for a in sys.argv[1:])
    inst_args = [a for a in sys.argv[1:] if a.upper() in INSTRUMENTS]
    iv_args   = [a for a in sys.argv[1:] if a in intervals]
    if not inst_args:
        inst_args = ["NQ"]          # defaut : Nasdaq
    if not iv_args:
        iv_args = ["1d"]            # defaut : journalier
    for inst_key in inst_args:
        for iv in iv_args:
            if do_swing:
                optimize_swing(inst_key.upper(), iv, intervals[iv])
            elif do_opt:
                optimize_fib(inst_key.upper(), iv, intervals[iv])
            else:
                run_one(inst_key.upper(), iv, intervals[iv])


if __name__ == "__main__":
    main()
