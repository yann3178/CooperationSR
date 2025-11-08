#!/usr/bin/env python3
"""
Download Historical Data

This script downloads historical price data using yfinance.

Usage:
    python download_data.py QQQ 2010-01-01 2024-12-31
"""

import sys
import argparse
from pathlib import Path


def download_data(symbol: str, start_date: str, end_date: str, output_dir: str = 'data'):
    """
    Download historical price data.

    Parameters:
    -----------
    symbol : str
        Ticker symbol (e.g., QQQ, SPY, AAPL)
    start_date : str
        Start date (YYYY-MM-DD)
    end_date : str
        End date (YYYY-MM-DD)
    output_dir : str
        Directory to save data
    """
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance not installed")
        print("Install with: pip install yfinance")
        sys.exit(1)

    print(f"Downloading {symbol} from {start_date} to {end_date}...")
    print("-" * 60)

    # Download data
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)

    if df.empty:
        print(f"ERROR: No data available for {symbol}")
        sys.exit(1)

    # Display info
    print(f"✓ Downloaded {len(df)} bars")
    print(f"  Date range: {df.index[0].date()} to {df.index[-1].date()}")
    print(f"  Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
    print()
    print("First few rows:")
    print(df.head())
    print()
    print("Last few rows:")
    print(df.tail())

    # Save to CSV
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    filename = f"{symbol}_{start_date}_{end_date}.csv"
    filepath = output_path / filename

    df.to_csv(filepath)
    print()
    print(f"✓ Data saved to: {filepath}")
    print()
    print("You can now use this data with:")
    print(f"  python main.py --data {filepath}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Download historical price data')

    parser.add_argument('symbol', type=str, help='Ticker symbol (e.g., QQQ, SPY)')
    parser.add_argument('start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, default='data',
                       help='Output directory (default: data)')

    args = parser.parse_args()

    download_data(args.symbol, args.start, args.end, args.output)


if __name__ == "__main__":
    main()
