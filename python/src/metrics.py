"""
Performance Metrics Module

This module calculates comprehensive performance metrics for backtesting results
including returns, risk metrics, and trade statistics.

Author: Renko Trend Following Strategy
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime


class PerformanceMetrics:
    """
    Calculate comprehensive performance metrics for trading strategies.
    """

    def __init__(self, trades_df: pd.DataFrame, equity_curve: pd.Series, initial_capital: float):
        """
        Initialize PerformanceMetrics.

        Parameters:
        -----------
        trades_df : pd.DataFrame
            DataFrame of completed trades
        equity_curve : pd.Series
            Time series of equity values
        initial_capital : float
            Starting capital
        """
        self.trades_df = trades_df
        self.equity_curve = equity_curve
        self.initial_capital = initial_capital

    def total_return(self) -> float:
        """Calculate total return percentage."""
        if self.equity_curve.empty:
            return 0.0
        final_equity = self.equity_curve.iloc[-1]
        return ((final_equity / self.initial_capital) - 1) * 100

    def total_trades(self) -> int:
        """Calculate total number of trades."""
        return len(self.trades_df)

    def winning_trades(self) -> int:
        """Calculate number of winning trades."""
        if self.trades_df.empty:
            return 0
        return len(self.trades_df[self.trades_df['pnl'] > 0])

    def losing_trades(self) -> int:
        """Calculate number of losing trades."""
        if self.trades_df.empty:
            return 0
        return len(self.trades_df[self.trades_df['pnl'] < 0])

    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        total = self.total_trades()
        if total == 0:
            return 0.0
        return (self.winning_trades() / total) * 100

    def average_win(self) -> float:
        """Calculate average winning trade."""
        if self.trades_df.empty:
            return 0.0
        wins = self.trades_df[self.trades_df['pnl'] > 0]['pnl']
        return wins.mean() if len(wins) > 0 else 0.0

    def average_loss(self) -> float:
        """Calculate average losing trade."""
        if self.trades_df.empty:
            return 0.0
        losses = self.trades_df[self.trades_df['pnl'] < 0]['pnl']
        return losses.mean() if len(losses) > 0 else 0.0

    def largest_win(self) -> float:
        """Calculate largest winning trade."""
        if self.trades_df.empty:
            return 0.0
        return self.trades_df['pnl'].max()

    def largest_loss(self) -> float:
        """Calculate largest losing trade."""
        if self.trades_df.empty:
            return 0.0
        return self.trades_df['pnl'].min()

    def profit_factor(self) -> float:
        """Calculate profit factor (gross profits / gross losses)."""
        if self.trades_df.empty:
            return 0.0

        gross_profit = self.trades_df[self.trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(self.trades_df[self.trades_df['pnl'] < 0]['pnl'].sum())

        if gross_loss == 0:
            return np.inf if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    def expectancy(self) -> float:
        """Calculate expectancy (average $ per trade)."""
        if self.trades_df.empty:
            return 0.0
        return self.trades_df['pnl'].mean()

    def max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage."""
        if self.equity_curve.empty:
            return 0.0

        cumulative_max = self.equity_curve.expanding().max()
        drawdown = (self.equity_curve - cumulative_max) / cumulative_max * 100

        return drawdown.min()

    def max_drawdown_dollars(self) -> float:
        """Calculate maximum drawdown in dollars."""
        if self.equity_curve.empty:
            return 0.0

        cumulative_max = self.equity_curve.expanding().max()
        drawdown_dollars = self.equity_curve - cumulative_max

        return drawdown_dollars.min()

    def max_drawdown_duration(self) -> Optional[int]:
        """Calculate maximum drawdown duration in days."""
        if self.equity_curve.empty or not isinstance(self.equity_curve.index, pd.DatetimeIndex):
            return None

        cumulative_max = self.equity_curve.expanding().max()
        is_drawdown = self.equity_curve < cumulative_max

        if not is_drawdown.any():
            return 0

        # Find drawdown periods
        drawdown_periods = []
        in_drawdown = False
        start_date = None

        for date, dd in is_drawdown.items():
            if dd and not in_drawdown:
                # Start of drawdown
                in_drawdown = True
                start_date = date
            elif not dd and in_drawdown:
                # End of drawdown
                in_drawdown = False
                duration = (date - start_date).days
                drawdown_periods.append(duration)

        if in_drawdown:
            # Still in drawdown at end
            duration = (self.equity_curve.index[-1] - start_date).days
            drawdown_periods.append(duration)

        return max(drawdown_periods) if drawdown_periods else 0

    def sharpe_ratio(self, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
        """
        Calculate annualized Sharpe ratio.

        Parameters:
        -----------
        risk_free_rate : float
            Annual risk-free rate (default 0.0)
        periods_per_year : int
            Number of periods per year (252 for daily, 12 for monthly)

        Returns:
        --------
        float
            Annualized Sharpe ratio
        """
        if self.equity_curve.empty or len(self.equity_curve) < 2:
            return 0.0

        returns = self.equity_curve.pct_change().dropna()

        if returns.std() == 0:
            return 0.0

        excess_returns = returns - (risk_free_rate / periods_per_year)
        sharpe = excess_returns.mean() / returns.std()

        return sharpe * np.sqrt(periods_per_year)

    def sortino_ratio(self, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
        """
        Calculate annualized Sortino ratio (uses downside deviation).

        Parameters:
        -----------
        risk_free_rate : float
            Annual risk-free rate (default 0.0)
        periods_per_year : int
            Number of periods per year

        Returns:
        --------
        float
            Annualized Sortino ratio
        """
        if self.equity_curve.empty or len(self.equity_curve) < 2:
            return 0.0

        returns = self.equity_curve.pct_change().dropna()
        excess_returns = returns - (risk_free_rate / periods_per_year)

        # Downside deviation (only negative returns)
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0

        sortino = excess_returns.mean() / downside_returns.std()

        return sortino * np.sqrt(periods_per_year)

    def calmar_ratio(self) -> float:
        """
        Calculate Calmar ratio (CAGR / Max Drawdown).

        Returns:
        --------
        float
            Calmar ratio
        """
        cagr = self.cagr()
        max_dd = abs(self.max_drawdown())

        if max_dd == 0:
            return 0.0

        return cagr / max_dd

    def cagr(self) -> float:
        """
        Calculate Compound Annual Growth Rate.

        Returns:
        --------
        float
            CAGR percentage
        """
        if self.equity_curve.empty or not isinstance(self.equity_curve.index, pd.DatetimeIndex):
            return 0.0

        start_date = self.equity_curve.index[0]
        end_date = self.equity_curve.index[-1]
        years = (end_date - start_date).days / 365.25

        if years == 0:
            return 0.0

        start_value = self.equity_curve.iloc[0]
        end_value = self.equity_curve.iloc[-1]

        cagr = (((end_value / start_value) ** (1 / years)) - 1) * 100

        return cagr

    def consecutive_wins(self) -> int:
        """Calculate maximum consecutive winning trades."""
        if self.trades_df.empty:
            return 0

        max_consecutive = 0
        current_consecutive = 0

        for pnl in self.trades_df['pnl']:
            if pnl > 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def consecutive_losses(self) -> int:
        """Calculate maximum consecutive losing trades."""
        if self.trades_df.empty:
            return 0

        max_consecutive = 0
        current_consecutive = 0

        for pnl in self.trades_df['pnl']:
            if pnl < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def average_trade_duration(self) -> Optional[float]:
        """Calculate average trade duration in days."""
        if self.trades_df.empty:
            return None

        if 'entry_date' in self.trades_df.columns and 'exit_date' in self.trades_df.columns:
            durations = (pd.to_datetime(self.trades_df['exit_date']) -
                        pd.to_datetime(self.trades_df['entry_date'])).dt.days
            return durations.mean()

        # Fallback to brick duration
        if 'duration_bricks' in self.trades_df.columns:
            return self.trades_df['duration_bricks'].mean()

        return None

    def get_all_metrics(self) -> Dict:
        """
        Calculate and return all metrics as a dictionary.

        Returns:
        --------
        Dict
            Dictionary containing all performance metrics
        """
        metrics = {
            # Performance
            'total_return_pct': self.total_return(),
            'total_return_dollars': self.equity_curve.iloc[-1] - self.initial_capital if not self.equity_curve.empty else 0,
            'cagr': self.cagr(),
            'initial_capital': self.initial_capital,
            'final_equity': self.equity_curve.iloc[-1] if not self.equity_curve.empty else self.initial_capital,

            # Trade Statistics
            'total_trades': self.total_trades(),
            'winning_trades': self.winning_trades(),
            'losing_trades': self.losing_trades(),
            'win_rate': self.win_rate(),
            'average_win': self.average_win(),
            'average_loss': self.average_loss(),
            'largest_win': self.largest_win(),
            'largest_loss': self.largest_loss(),
            'profit_factor': self.profit_factor(),
            'expectancy': self.expectancy(),

            # Risk Metrics
            'max_drawdown_pct': self.max_drawdown(),
            'max_drawdown_dollars': self.max_drawdown_dollars(),
            'max_drawdown_duration_days': self.max_drawdown_duration(),
            'sharpe_ratio': self.sharpe_ratio(),
            'sortino_ratio': self.sortino_ratio(),
            'calmar_ratio': self.calmar_ratio(),

            # Distribution
            'consecutive_wins': self.consecutive_wins(),
            'consecutive_losses': self.consecutive_losses(),
            'average_trade_duration': self.average_trade_duration(),
        }

        return metrics

    def print_report(self):
        """Print a formatted performance report."""
        metrics = self.get_all_metrics()

        print("=" * 60)
        print("PERFORMANCE REPORT")
        print("=" * 60)
        print()

        print("PERFORMANCE METRICS")
        print("-" * 60)
        print(f"Initial Capital:        ${metrics['initial_capital']:,.2f}")
        print(f"Final Equity:           ${metrics['final_equity']:,.2f}")
        print(f"Total Return:           {metrics['total_return_pct']:.2f}%")
        print(f"Total Return ($):       ${metrics['total_return_dollars']:,.2f}")
        print(f"CAGR:                   {metrics['cagr']:.2f}%")
        print()

        print("TRADE STATISTICS")
        print("-" * 60)
        print(f"Total Trades:           {metrics['total_trades']}")
        print(f"Winning Trades:         {metrics['winning_trades']}")
        print(f"Losing Trades:          {metrics['losing_trades']}")
        print(f"Win Rate:               {metrics['win_rate']:.2f}%")
        print(f"Average Win:            ${metrics['average_win']:,.2f}")
        print(f"Average Loss:           ${metrics['average_loss']:,.2f}")
        print(f"Largest Win:            ${metrics['largest_win']:,.2f}")
        print(f"Largest Loss:           ${metrics['largest_loss']:,.2f}")
        print(f"Profit Factor:          {metrics['profit_factor']:.2f}")
        print(f"Expectancy:             ${metrics['expectancy']:,.2f}")
        print()

        print("RISK METRICS")
        print("-" * 60)
        print(f"Max Drawdown:           {metrics['max_drawdown_pct']:.2f}%")
        print(f"Max Drawdown ($):       ${metrics['max_drawdown_dollars']:,.2f}")
        dd_duration = metrics['max_drawdown_duration_days']
        print(f"Max DD Duration:        {dd_duration if dd_duration is not None else 'N/A'} days")
        print(f"Sharpe Ratio:           {metrics['sharpe_ratio']:.2f}")
        print(f"Sortino Ratio:          {metrics['sortino_ratio']:.2f}")
        print(f"Calmar Ratio:           {metrics['calmar_ratio']:.2f}")
        print()

        print("DISTRIBUTION")
        print("-" * 60)
        print(f"Consecutive Wins:       {metrics['consecutive_wins']}")
        print(f"Consecutive Losses:     {metrics['consecutive_losses']}")
        avg_duration = metrics['average_trade_duration']
        if avg_duration is not None:
            print(f"Avg Trade Duration:     {avg_duration:.1f}")
        else:
            print(f"Avg Trade Duration:     N/A")
        print()
        print("=" * 60)


def compare_to_buy_hold(
    strategy_equity: pd.Series,
    buy_hold_equity: pd.Series,
    initial_capital: float
) -> Dict:
    """
    Compare strategy performance to buy-and-hold.

    Parameters:
    -----------
    strategy_equity : pd.Series
        Strategy equity curve
    buy_hold_equity : pd.Series
        Buy-and-hold equity curve
    initial_capital : float
        Initial capital

    Returns:
    --------
    Dict
        Comparison metrics
    """
    strategy_return = ((strategy_equity.iloc[-1] / initial_capital) - 1) * 100
    bh_return = ((buy_hold_equity.iloc[-1] / initial_capital) - 1) * 100

    # Calculate Sharpe for both
    strategy_returns = strategy_equity.pct_change().dropna()
    bh_returns = buy_hold_equity.pct_change().dropna()

    strategy_sharpe = (strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)) if strategy_returns.std() > 0 else 0
    bh_sharpe = (bh_returns.mean() / bh_returns.std() * np.sqrt(252)) if bh_returns.std() > 0 else 0

    return {
        'strategy_return': strategy_return,
        'buy_hold_return': bh_return,
        'outperformance': strategy_return - bh_return,
        'strategy_sharpe': strategy_sharpe,
        'buy_hold_sharpe': bh_sharpe,
    }


if __name__ == "__main__":
    print("Performance Metrics Module")
    print("==========================")
    print()
    print("This module calculates comprehensive performance metrics.")
    print("Use with backtest.py for complete analysis.")
