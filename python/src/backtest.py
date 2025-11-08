"""
Backtest Engine

This module orchestrates the complete backtesting process including data loading,
Renko construction, strategy execution, and results visualization.

Author: Renko Trend Following Strategy
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
from pathlib import Path
import json

# Make matplotlib optional
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from renko import RenkoBuilder
from strategy import RenkoTrendStrategy, StrategyConfig
from metrics import PerformanceMetrics, compare_to_buy_hold


class Backtest:
    """
    Complete backtesting engine for Renko Trend Following strategy.
    """

    def __init__(
        self,
        price_data: pd.DataFrame,
        strategy_config: StrategyConfig,
        brick_type: str = "PERCENTAGE",
        brick_size: float = 0.01,
        atr_period: int = 14
    ):
        """
        Initialize backtest.

        Parameters:
        -----------
        price_data : pd.DataFrame
            OHLC price data with DatetimeIndex
        strategy_config : StrategyConfig
            Strategy configuration
        brick_type : str
            Renko brick type
        brick_size : float
            Renko brick size
        atr_period : int
            ATR period for ATR-based bricks
        """
        self.price_data = price_data
        self.strategy_config = strategy_config
        self.brick_type = brick_type
        self.brick_size = brick_size
        self.atr_period = atr_period

        self.renko_df = None
        self.strategy = None
        self.results_df = None
        self.trades_df = None
        self.metrics = None

    def run(self) -> Dict:
        """
        Run complete backtest.

        Returns:
        --------
        Dict
            Backtest results summary
        """
        print("Starting backtest...")
        print("=" * 60)

        # Step 1: Build Renko bricks
        print(f"\n[1/4] Building Renko bricks ({self.brick_type}, size={self.brick_size})...")
        renko_builder = RenkoBuilder(self.brick_type, self.brick_size, self.atr_period)
        self.renko_df = renko_builder.build_renko(self.price_data)
        print(f"✓ Created {len(self.renko_df)} Renko bricks from {len(self.price_data)} price bars")

        # Step 2: Run strategy
        print(f"\n[2/4] Running strategy...")
        self.strategy = RenkoTrendStrategy(self.strategy_config)
        self.results_df = self.strategy.run(self.renko_df, self.price_data)
        self.trades_df = self.strategy.get_trades_df()
        print(f"✓ Executed {len(self.trades_df)} trades")

        # Step 3: Calculate metrics
        print(f"\n[3/4] Calculating performance metrics...")
        equity_curve = self.results_df.set_index('datetime')['equity']
        self.metrics = PerformanceMetrics(
            self.trades_df,
            equity_curve,
            self.strategy_config.initial_capital
        )
        all_metrics = self.metrics.get_all_metrics()
        print(f"✓ Performance: {all_metrics['total_return_pct']:.2f}% return, "
              f"{all_metrics['max_drawdown_pct']:.2f}% max DD, "
              f"Sharpe: {all_metrics['sharpe_ratio']:.2f}")

        # Step 4: Calculate buy-and-hold comparison
        print(f"\n[4/4] Calculating buy-and-hold comparison...")
        bh_metrics = self._calculate_buy_hold()
        print(f"✓ Buy-and-hold return: {bh_metrics['return']:.2f}%")

        print("\n" + "=" * 60)
        print("Backtest complete!")

        # Summary
        summary = {
            'total_bars': len(self.price_data),
            'total_bricks': len(self.renko_df),
            'total_trades': len(self.trades_df),
            'metrics': all_metrics,
            'buy_hold': bh_metrics
        }

        return summary

    def _calculate_buy_hold(self) -> Dict:
        """
        Calculate buy-and-hold returns.

        Returns:
        --------
        Dict
            Buy-and-hold metrics
        """
        if self.price_data.empty:
            return {'return': 0.0, 'equity': []}

        # Calculate buy-and-hold equity
        start_price = self.price_data.iloc[0]['close']
        shares = self.strategy_config.initial_capital / start_price

        bh_equity = self.price_data['close'] * shares
        bh_return = ((bh_equity.iloc[-1] / self.strategy_config.initial_capital) - 1) * 100

        return {
            'return': bh_return,
            'equity': bh_equity,
            'shares': shares
        }

    def plot_results(self, save_path: Optional[str] = None):
        """
        Plot backtest results.

        Parameters:
        -----------
        save_path : str, optional
            Path to save plot
        """
        if not MATPLOTLIB_AVAILABLE:
            print("Warning: matplotlib not available. Install with: pip install matplotlib")
            return

        if self.results_df is None:
            raise ValueError("No results to plot. Run backtest first.")

        fig, axes = plt.subplots(3, 1, figsize=(14, 10))

        # Plot 1: Equity Curve
        ax1 = axes[0]
        equity_curve = self.results_df.set_index('datetime')['equity']
        bh_equity = self._calculate_buy_hold()['equity']

        ax1.plot(equity_curve.index, equity_curve.values, label='Strategy', linewidth=2)
        ax1.plot(bh_equity.index, bh_equity.values, label='Buy & Hold', alpha=0.7, linestyle='--')
        ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Equity ($)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

        # Plot 2: Drawdown
        ax2 = axes[1]
        cumulative_max = equity_curve.expanding().max()
        drawdown = (equity_curve - cumulative_max) / cumulative_max * 100

        ax2.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
        ax2.plot(drawdown.index, drawdown.values, color='red', linewidth=1)
        ax2.set_title('Drawdown', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

        # Plot 3: Trade P&L Distribution
        ax3 = axes[2]
        if not self.trades_df.empty:
            wins = self.trades_df[self.trades_df['pnl'] > 0]['pnl']
            losses = self.trades_df[self.trades_df['pnl'] < 0]['pnl']

            ax3.hist(wins, bins=20, alpha=0.7, color='green', label='Wins')
            ax3.hist(losses, bins=20, alpha=0.7, color='red', label='Losses')
            ax3.axvline(x=0, color='black', linestyle='--', linewidth=1)
            ax3.set_title('Trade P&L Distribution', fontsize=14, fontweight='bold')
            ax3.set_xlabel('P&L ($)')
            ax3.set_ylabel('Frequency')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, 'No trades executed', ha='center', va='center',
                    transform=ax3.transAxes, fontsize=12)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Plot saved to: {save_path}")

        plt.show()

    def plot_renko_with_signals(self, save_path: Optional[str] = None):
        """
        Plot Renko bricks with entry/exit signals.

        Parameters:
        -----------
        save_path : str, optional
            Path to save plot
        """
        if not MATPLOTLIB_AVAILABLE:
            print("Warning: matplotlib not available. Install with: pip install matplotlib")
            return

        if self.results_df is None:
            raise ValueError("No results to plot. Run backtest first.")

        fig, ax = plt.subplots(figsize=(14, 8))

        # Plot Renko bricks
        for idx, brick in self.results_df.iterrows():
            color = 'green' if brick['color'] == 'GREEN' else 'red'
            ax.add_patch(plt.Rectangle(
                (idx, brick['low']),
                1,
                brick['high'] - brick['low'],
                facecolor=color,
                edgecolor='black',
                alpha=0.6
            ))

        # Plot entry signals
        long_entries = self.results_df[self.results_df['signal'] == 'LONG_ENTRY']
        short_entries = self.results_df[self.results_df['signal'] == 'SHORT_ENTRY']

        if not long_entries.empty:
            ax.scatter(long_entries.index, long_entries['close'],
                      marker='^', color='blue', s=100, label='Long Entry', zorder=5)

        if not short_entries.empty:
            ax.scatter(short_entries.index, short_entries['close'],
                      marker='v', color='orange', s=100, label='Short Entry', zorder=5)

        # Plot SMA if available
        if 'sma' in self.results_df.columns:
            sma_values = self.results_df['sma'].dropna()
            if not sma_values.empty:
                ax.plot(sma_values.index, sma_values.values,
                       label=f'SMA({self.strategy_config.trend_sma_period})',
                       color='purple', linewidth=2, alpha=0.7)

        ax.set_title('Renko Bricks with Trading Signals', fontsize=14, fontweight='bold')
        ax.set_xlabel('Brick Number')
        ax.set_ylabel('Price')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Plot saved to: {save_path}")

        plt.show()

    def export_results(self, output_dir: str):
        """
        Export backtest results to files.

        Parameters:
        -----------
        output_dir : str
            Directory to save results
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export trades
        if not self.trades_df.empty:
            trades_file = output_path / 'trades.csv'
            self.trades_df.to_csv(trades_file, index=False)
            print(f"✓ Trades exported to: {trades_file}")

        # Export Renko data with signals
        if self.results_df is not None:
            renko_file = output_path / 'renko_signals.csv'
            self.results_df.to_csv(renko_file, index=False)
            print(f"✓ Renko signals exported to: {renko_file}")

        # Export metrics
        if self.metrics is not None:
            metrics_file = output_path / 'metrics.json'
            metrics_dict = self.metrics.get_all_metrics()

            # Convert to JSON-serializable format
            metrics_json = {}
            for key, value in metrics_dict.items():
                if pd.isna(value):
                    metrics_json[key] = None
                elif isinstance(value, (np.integer, np.floating)):
                    metrics_json[key] = float(value)
                else:
                    metrics_json[key] = value

            with open(metrics_file, 'w') as f:
                json.dump(metrics_json, f, indent=2)
            print(f"✓ Metrics exported to: {metrics_file}")

        # Export configuration
        config_file = output_path / 'config.json'
        config_dict = {
            'strategy': self.strategy_config.to_dict(),
            'renko': {
                'brick_type': self.brick_type,
                'brick_size': self.brick_size,
                'atr_period': self.atr_period
            }
        }
        with open(config_file, 'w') as f:
            json.dump(config_dict, f, indent=2)
        print(f"✓ Configuration exported to: {config_file}")

        print(f"\nAll results exported to: {output_path}")

    def print_report(self):
        """Print comprehensive backtest report."""
        if self.metrics is None:
            raise ValueError("No metrics available. Run backtest first.")

        print("\n")
        self.metrics.print_report()

        # Add comparison to buy-and-hold
        if self.price_data is not None:
            bh_metrics = self._calculate_buy_hold()
            strategy_return = self.metrics.total_return()

            print("COMPARISON TO BUY-AND-HOLD")
            print("-" * 60)
            print(f"Strategy Return:        {strategy_return:.2f}%")
            print(f"Buy-and-Hold Return:    {bh_metrics['return']:.2f}%")
            print(f"Outperformance:         {strategy_return - bh_metrics['return']:.2f}%")
            print("=" * 60)


def load_price_data(filepath: str) -> pd.DataFrame:
    """
    Load price data from CSV file.

    Parameters:
    -----------
    filepath : str
        Path to CSV file

    Returns:
    --------
    pd.DataFrame
        Price data with DatetimeIndex
    """
    df = pd.read_csv(filepath)

    # Parse datetime
    datetime_cols = ['datetime', 'date', 'timestamp', 'time', 'Date']
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
            df.set_index(col, inplace=True)
            break

    # Standardize column names
    column_mapping = {}
    for col in df.columns:
        lower_col = col.lower()
        if lower_col in ['open', 'high', 'low', 'close', 'volume', 'adj close']:
            column_mapping[col] = lower_col.replace(' ', '_')

    df.rename(columns=column_mapping, inplace=True)

    # Use adjusted close if available
    if 'adj_close' in df.columns:
        df['close'] = df['adj_close']

    return df


if __name__ == "__main__":
    print("Backtest Engine")
    print("===============")
    print()
    print("This module orchestrates the complete backtesting process.")
    print("Use main.py for running backtests with your data.")
