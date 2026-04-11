"""Download all candidate instruments and persist as parquet for fast reuse."""
import os
import pandas as pd
import yfinance as yf

OUT = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT, exist_ok=True)

TICKERS = {
    # Nasdaq and leveraged cousins
    "QQQ": "Nasdaq 100 ETF",
    "TQQQ": "3x Nasdaq 100 ETF (from 2010)",
    "QLD": "2x Nasdaq 100 ETF (from 2006)",
    "PSQ": "Inverse Nasdaq 100 (from 2006)",
    # Broad equity
    "SPY": "S&P 500 ETF",
    "IWM": "Russell 2000 ETF",
    "EFA": "MSCI EAFE ETF",
    # Bonds / Cash / Duration
    "SHY": "1-3Y Treasury ETF",
    "IEF": "7-10Y Treasury ETF",
    "TLT": "20+Y Treasury ETF",
    "BIL": "1-3M T-Bill ETF",
    # Alts
    "GLD": "Gold ETF",
    "SLV": "Silver ETF",
    "USO": "Crude Oil ETF",
    "DBC": "Diversified commodities",
    # Volatility
    "^VIX": "VIX index",
    "^VXN": "Nasdaq vol index",
    # Benchmarks and macro
    "^GSPC": "S&P 500 index",
    "^NDX": "Nasdaq 100 index",
    "^TNX": "10Y Treasury yield",
    "^IRX": "3M Treasury yield",
    # Defensive
    "XLP": "Consumer Staples ETF",
    "XLU": "Utilities ETF",
    "XLV": "Healthcare ETF",
}

END = "2026-04-11"

for tk in TICKERS:
    try:
        print(f"Downloading {tk}...", end=" ", flush=True)
        df = yf.download(tk, start="1990-01-01", end=END,
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        if df.empty:
            print("EMPTY")
            continue
        df.to_csv(os.path.join(OUT, f"{tk.replace('^','').replace('=','')}.csv"))
        print(f"{df.index[0].date()} -> {df.index[-1].date()} ({len(df)} rows)")
    except Exception as e:
        print(f"FAIL {e}")

print("Done.")
