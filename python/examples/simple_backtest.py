#!/usr/bin/env python3
"""
Simple Backtest Example

This is a minimal example showing how to run a backtest
of the Renko Trend Following strategy.

Usage:
    python simple_backtest.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import numpy as np
from backtest import Backtest
from strategy import StrategyConfig


def create_sample_data():
    """Create sample price data for demonstration."""
    print("Creating sample data...")

    # Generate 500 days of price data with an uptrend
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=500, freq='D')

    # Simulate price with trend and noise
    trend = np.linspace(100, 150, 500)
    noise = np.random.randn(500) * 3
    prices = trend + noise

    # Create OHLC data
    data = pd.DataFrame({
        'open': prices + np.random.randn(500) * 0.5,
        'high': prices + np.abs(np.random.randn(500) * 2),
        'low': prices - np.abs(np.random.randn(500) * 2),
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, 500)
    }, index=dates)

    print(f"✓ Created {len(data)} days of sample data")
    print(f"  Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")

    return data


def main():
    """Run simple backtest example."""
    print("=" * 60)
    print("RENKO TREND FOLLOWING - SIMPLE BACKTEST EXAMPLE")
    print("=" * 60)
    print()

    # Step 1: Get price data
    # Option A: Use sample data
    price_data = create_sample_data()

    # Option B: Load from CSV (uncomment to use)
    # from backtest import load_price_data
    # price_data = load_price_data('path/to/your/data.csv')

    # Step 2: Configure strategy
    print("\nConfiguring strategy...")
    config = StrategyConfig(
        # Trend Filter
        use_trend_filter=True,
        trend_sma_period=50,  # Shorter period for demo data
        trend_margin=0.00,

        # Entry
        entry_confirm_type="FIRST_GREEN",
        require_no_wick=False,
        require_prior_red=True,

        # Direction
        allow_long=True,
        allow_short=False,

        # Position Sizing
        position_size_type="PERCENT_EQUITY",
        position_size_value=0.90,
        initial_capital=10000,

        # Exit
        stop_trail=True,
        exit_on_reverse_brick=True
    )

    print("✓ Strategy configured")
    print(f"  Initial Capital: ${config.initial_capital:,.2f}")
    print(f"  Position Size: {config.position_size_value * 100:.0f}% of equity")
    print(f"  Trend Filter: SMA({config.trend_sma_period})")

    # Step 3: Run backtest
    print("\nRunning backtest...")
    backtest = Backtest(
        price_data=price_data,
        strategy_config=config,
        brick_type="PERCENTAGE",
        brick_size=0.02  # 2% bricks
    )

    summary = backtest.run()

    # Step 4: Display results
    print("\n")
    backtest.print_report()

    # Step 5: Show trades
    print("\n" + "=" * 60)
    print("TRADE HISTORY")
    print("=" * 60)

    trades_df = backtest.trades_df
    if not trades_df.empty:
        print(trades_df[['entry_date', 'direction', 'entry_price',
                        'exit_price', 'pnl', 'pnl_pct']].to_string(index=False))
    else:
        print("No trades executed")

    # Step 6: Plot results (optional)
    print("\n" + "=" * 60)
    print("VISUALIZATION")
    print("=" * 60)

    try:
        print("\nGenerating plots...")
        backtest.plot_results()
        print("✓ Plots displayed")
    except Exception as e:
        print(f"Could not display plots: {e}")
        print("(This is normal if running without display)")

    print("\n" + "=" * 60)
    print("EXAMPLE COMPLETE")
    print("=" * 60)

    # Summary
    metrics = backtest.metrics.get_all_metrics()
    print(f"\n📊 Summary:")
    print(f"   Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"   Total Trades: {metrics['total_trades']}")
    print(f"   Win Rate: {metrics['win_rate']:.2f}%")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")

    print("\n💡 Next steps:")
    print("   1. Try with real data: load_price_data('your_data.csv')")
    print("   2. Experiment with different brick sizes")
    print("   3. Optimize SMA period for your instrument")
    print("   4. Run walk-forward analysis")
    print("   5. Check out the Jupyter notebook for interactive analysis")


if __name__ == "__main__":
    main()
