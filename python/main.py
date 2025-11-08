#!/usr/bin/env python3
"""
Renko Trend Following Strategy - Main Execution Script

This script runs a complete backtest of the Renko Trend Following strategy
on historical price data.

Usage:
    python main.py --symbol QQQ --start 2010-01-01 --end 2024-12-31

Author: Renko Trend Following Strategy
Version: 1.0.0
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from backtest import Backtest, load_price_data
from strategy import StrategyConfig


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Renko Trend Following Strategy Backtest'
    )

    parser.add_argument(
        '--data',
        type=str,
        help='Path to CSV file with price data'
    )

    parser.add_argument(
        '--symbol',
        type=str,
        default='QQQ',
        help='Symbol to backtest (used if --data not provided)'
    )

    parser.add_argument(
        '--start',
        type=str,
        default='2010-01-01',
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        default='2024-12-31',
        help='End date (YYYY-MM-DD)'
    )

    # Renko configuration
    parser.add_argument(
        '--brick-type',
        type=str,
        default='PERCENTAGE',
        choices=['PERCENTAGE', 'FIXED_POINTS', 'ATR_BASED'],
        help='Renko brick type'
    )

    parser.add_argument(
        '--brick-size',
        type=float,
        default=0.01,
        help='Renko brick size (0.01 = 1%% for PERCENTAGE)'
    )

    parser.add_argument(
        '--atr-period',
        type=int,
        default=14,
        help='ATR period for ATR_BASED brick type'
    )

    # Strategy configuration
    parser.add_argument(
        '--sma-period',
        type=int,
        default=200,
        help='SMA period for trend filter'
    )

    parser.add_argument(
        '--no-trend-filter',
        action='store_true',
        help='Disable trend filter'
    )

    parser.add_argument(
        '--allow-short',
        action='store_true',
        help='Enable short positions'
    )

    parser.add_argument(
        '--entry-confirm',
        type=str,
        default='FIRST_GREEN',
        choices=['FIRST_GREEN', 'SECOND_GREEN'],
        help='Entry confirmation type'
    )

    parser.add_argument(
        '--initial-capital',
        type=float,
        default=30000,
        help='Initial capital'
    )

    parser.add_argument(
        '--position-size',
        type=float,
        default=0.90,
        help='Position size (0.90 = 90%% of equity)'
    )

    # Output options
    parser.add_argument(
        '--output-dir',
        type=str,
        default='outputs',
        help='Directory to save results'
    )

    parser.add_argument(
        '--no-plot',
        action='store_true',
        help='Disable plotting'
    )

    return parser.parse_args()


def download_data(symbol: str, start_date: str, end_date: str) -> Path:
    """
    Download price data using yfinance.

    Parameters:
    -----------
    symbol : str
        Ticker symbol
    start_date : str
        Start date
    end_date : str
        End date

    Returns:
    --------
    Path
        Path to saved CSV file
    """
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance not installed. Install with: pip install yfinance")
        print("Or provide data file with --data option")
        sys.exit(1)

    print(f"Downloading {symbol} data from {start_date} to {end_date}...")

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)

    if df.empty:
        print(f"ERROR: No data downloaded for {symbol}")
        sys.exit(1)

    # Save to data directory
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)

    filepath = data_dir / f'{symbol}_{start_date}_{end_date}.csv'
    df.to_csv(filepath)

    print(f"✓ Data saved to: {filepath}")
    print(f"  Rows: {len(df)}, Date range: {df.index[0].date()} to {df.index[-1].date()}")

    return filepath


def main():
    """Main execution function."""
    args = parse_args()

    print("=" * 70)
    print("RENKO TREND FOLLOWING STRATEGY - BACKTEST")
    print("=" * 70)
    print()

    # Load or download data
    if args.data:
        data_file = Path(args.data)
        if not data_file.exists():
            print(f"ERROR: Data file not found: {data_file}")
            sys.exit(1)
        print(f"Loading data from: {data_file}")
    else:
        data_file = download_data(args.symbol, args.start, args.end)

    price_data = load_price_data(str(data_file))
    print(f"✓ Loaded {len(price_data)} price bars")
    print(f"  Date range: {price_data.index[0].date()} to {price_data.index[-1].date()}")
    print()

    # Configure strategy
    config = StrategyConfig(
        use_trend_filter=not args.no_trend_filter,
        trend_sma_period=args.sma_period,
        trend_margin=0.00,
        entry_confirm_type=args.entry_confirm,
        require_no_wick=False,
        require_prior_red=True,
        allow_long=True,
        allow_short=args.allow_short,
        short_trend_filter=True,
        position_size_type="PERCENT_EQUITY",
        position_size_value=args.position_size,
        initial_capital=args.initial_capital,
        stop_type="PREVIOUS_BRICK",
        stop_intraday=True,
        stop_trail=True,
        exit_on_reverse_brick=True
    )

    print("CONFIGURATION")
    print("-" * 70)
    print(f"Renko Type:             {args.brick_type}")
    print(f"Brick Size:             {args.brick_size}")
    print(f"Trend Filter:           {'Enabled' if config.use_trend_filter else 'Disabled'}")
    print(f"SMA Period:             {config.trend_sma_period}")
    print(f"Entry Confirmation:     {config.entry_confirm_type}")
    print(f"Allow Long:             {config.allow_long}")
    print(f"Allow Short:            {config.allow_short}")
    print(f"Position Size:          {config.position_size_value * 100:.0f}% of equity")
    print(f"Initial Capital:        ${config.initial_capital:,.2f}")
    print()

    # Run backtest
    backtest = Backtest(
        price_data=price_data,
        strategy_config=config,
        brick_type=args.brick_type,
        brick_size=args.brick_size,
        atr_period=args.atr_period
    )

    summary = backtest.run()

    # Print report
    backtest.print_report()

    # Export results
    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    symbol_name = args.symbol if not args.data else Path(args.data).stem
    results_dir = output_dir / f'{symbol_name}_{timestamp}'

    backtest.export_results(str(results_dir))

    # Plot results
    if not args.no_plot:
        print("\nGenerating plots...")
        try:
            backtest.plot_results(str(results_dir / 'equity_curve.png'))
            backtest.plot_renko_with_signals(str(results_dir / 'renko_signals.png'))
            print("✓ Plots generated successfully")
        except Exception as e:
            print(f"Warning: Could not generate plots: {e}")
            print("(This is normal if running without display or missing matplotlib)")

    print("\n" + "=" * 70)
    print("BACKTEST COMPLETE")
    print("=" * 70)
    print(f"\nResults saved to: {results_dir}")
    print("\nNext steps:")
    print("1. Review the performance report above")
    print("2. Check the exported files in the results directory")
    print("3. Analyze the equity curve and trade distribution plots")
    print("4. Optimize parameters if needed")
    print("5. Run walk-forward analysis for validation")


if __name__ == "__main__":
    main()
