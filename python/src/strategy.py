"""
Renko Trend Following Strategy

This module implements the core trading logic for the Renko Trend Following strategy
with trend filters, trailing stops, and comprehensive risk management.

Author: Renko Trend Following Strategy
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from typing import Literal, Optional, Dict, List
from dataclasses import dataclass


@dataclass
class StrategyConfig:
    """Configuration parameters for the Renko Trend Following strategy."""

    # Trend Filter
    use_trend_filter: bool = True
    trend_sma_period: int = 200
    trend_margin: float = 0.00

    # Entry Conditions
    entry_confirm_type: Literal["FIRST_GREEN", "SECOND_GREEN"] = "FIRST_GREEN"
    require_no_wick: bool = False
    require_prior_red: bool = True

    # Trading Direction
    allow_long: bool = True
    allow_short: bool = False
    short_trend_filter: bool = True

    # Position Sizing
    position_size_type: Literal["FIXED", "PERCENT_EQUITY"] = "PERCENT_EQUITY"
    position_size_value: float = 0.90
    initial_capital: float = 30000.0

    # Stop Management
    stop_type: Literal["PREVIOUS_BRICK"] = "PREVIOUS_BRICK"
    stop_intraday: bool = True
    stop_trail: bool = True
    exit_on_reverse_brick: bool = True

    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return {
            'use_trend_filter': self.use_trend_filter,
            'trend_sma_period': self.trend_sma_period,
            'trend_margin': self.trend_margin,
            'entry_confirm_type': self.entry_confirm_type,
            'require_no_wick': self.require_no_wick,
            'require_prior_red': self.require_prior_red,
            'allow_long': self.allow_long,
            'allow_short': self.allow_short,
            'short_trend_filter': self.short_trend_filter,
            'position_size_type': self.position_size_type,
            'position_size_value': self.position_size_value,
            'initial_capital': self.initial_capital,
            'stop_type': self.stop_type,
            'stop_intraday': self.stop_intraday,
            'stop_trail': self.stop_trail,
            'exit_on_reverse_brick': self.exit_on_reverse_brick,
        }


class RenkoTrendStrategy:
    """
    Renko Trend Following Strategy implementation.

    This class implements the complete trading logic including entry/exit conditions,
    position sizing, and stop management.
    """

    def __init__(self, config: StrategyConfig):
        """
        Initialize strategy.

        Parameters:
        -----------
        config : StrategyConfig
            Strategy configuration parameters
        """
        self.config = config
        self.position = None  # Current position: None, 'LONG', or 'SHORT'
        self.entry_price = None
        self.stop_level = None
        self.position_size = 0
        self.trades = []
        self.equity = config.initial_capital

    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average.

        Parameters:
        -----------
        prices : pd.Series
            Price series
        period : int
            SMA period

        Returns:
        --------
        pd.Series
            SMA values
        """
        return prices.rolling(window=period).mean()

    def check_trend_filter_long(self, price: float, sma_value: float) -> bool:
        """
        Check if price satisfies trend filter for long entry.

        Parameters:
        -----------
        price : float
            Current price
        sma_value : float
            SMA value

        Returns:
        --------
        bool
            True if trend filter is satisfied
        """
        if not self.config.use_trend_filter:
            return True

        if pd.isna(sma_value):
            return False

        threshold = sma_value * (1 + self.config.trend_margin)
        return price > threshold

    def check_trend_filter_short(self, price: float, sma_value: float) -> bool:
        """
        Check if price satisfies trend filter for short entry.

        Parameters:
        -----------
        price : float
            Current price
        sma_value : float
            SMA value

        Returns:
        --------
        bool
            True if trend filter is satisfied
        """
        if not self.config.use_trend_filter:
            return True

        if not self.config.short_trend_filter:
            return True

        if pd.isna(sma_value):
            return False

        threshold = sma_value * (1 - self.config.trend_margin)
        return price < threshold

    def calculate_position_size(self, price: float) -> int:
        """
        Calculate position size based on configuration.

        Parameters:
        -----------
        price : float
            Entry price

        Returns:
        --------
        int
            Number of shares/contracts to trade
        """
        if self.config.position_size_type == "FIXED":
            return int(self.config.position_size_value)

        # PERCENT_EQUITY
        equity_to_use = self.equity * self.config.position_size_value
        shares = int(equity_to_use / price)
        return max(shares, 1)  # At least 1 share

    def check_long_entry(
        self,
        brick: pd.Series,
        previous_brick: Optional[pd.Series],
        sma_value: float
    ) -> bool:
        """
        Check if long entry conditions are met.

        Parameters:
        -----------
        brick : pd.Series
            Current brick data
        previous_brick : pd.Series, optional
            Previous brick data
        sma_value : float
            Current SMA value

        Returns:
        --------
        bool
            True if long entry conditions are satisfied
        """
        # Check if long trading is allowed
        if not self.config.allow_long:
            return False

        # Check if already in position
        if self.position is not None:
            return False

        # Check brick color
        if brick['color'] != 'GREEN':
            return False

        # Check confirmation type
        if self.config.entry_confirm_type == "SECOND_GREEN":
            if brick.get('consecutive_same_color', 0) < 2:
                return False

        # Check no wick requirement
        if self.config.require_no_wick:
            if brick.get('has_lower_wick', False):
                return False

        # Check prior red requirement
        if self.config.require_prior_red:
            if previous_brick is None:
                return False
            if brick.get('consecutive_same_color', 0) > 1:
                # Not the first brick of this color
                return False
            if previous_brick['color'] != 'RED':
                return False

        # Check trend filter
        if not self.check_trend_filter_long(brick['close'], sma_value):
            return False

        return True

    def check_short_entry(
        self,
        brick: pd.Series,
        previous_brick: Optional[pd.Series],
        sma_value: float
    ) -> bool:
        """
        Check if short entry conditions are met.

        Parameters:
        -----------
        brick : pd.Series
            Current brick data
        previous_brick : pd.Series, optional
            Previous brick data
        sma_value : float
            Current SMA value

        Returns:
        --------
        bool
            True if short entry conditions are satisfied
        """
        # Check if short trading is allowed
        if not self.config.allow_short:
            return False

        # Check if already in position
        if self.position is not None:
            return False

        # Check brick color
        if brick['color'] != 'RED':
            return False

        # Check confirmation type
        if self.config.entry_confirm_type == "SECOND_GREEN":
            if brick.get('consecutive_same_color', 0) < 2:
                return False

        # Check no wick requirement
        if self.config.require_no_wick:
            if brick.get('has_upper_wick', False):
                return False

        # Check prior green requirement
        if self.config.require_prior_red:
            if previous_brick is None:
                return False
            if brick.get('consecutive_same_color', 0) > 1:
                # Not the first brick of this color
                return False
            if previous_brick['color'] != 'GREEN':
                return False

        # Check trend filter
        if not self.check_trend_filter_short(brick['close'], sma_value):
            return False

        return True

    def enter_long(self, brick: pd.Series, previous_brick: pd.Series):
        """
        Enter long position.

        Parameters:
        -----------
        brick : pd.Series
            Current brick (entry brick)
        previous_brick : pd.Series
            Previous brick
        """
        self.position = 'LONG'
        self.entry_price = brick['close']
        self.stop_level = previous_brick['close']
        self.position_size = self.calculate_position_size(self.entry_price)

        # Start trade record
        self.current_trade = {
            'entry_date': brick['datetime'],
            'entry_price': self.entry_price,
            'direction': 'LONG',
            'position_size': self.position_size,
            'entry_brick_number': brick['brick_number']
        }

    def enter_short(self, brick: pd.Series, previous_brick: pd.Series):
        """
        Enter short position.

        Parameters:
        -----------
        brick : pd.Series
            Current brick (entry brick)
        previous_brick : pd.Series
            Previous brick
        """
        self.position = 'SHORT'
        self.entry_price = brick['close']
        self.stop_level = previous_brick['close']
        self.position_size = self.calculate_position_size(self.entry_price)

        # Start trade record
        self.current_trade = {
            'entry_date': brick['datetime'],
            'entry_price': self.entry_price,
            'direction': 'SHORT',
            'position_size': self.position_size,
            'entry_brick_number': brick['brick_number']
        }

    def update_trailing_stop_long(self, brick: pd.Series, previous_brick: pd.Series):
        """
        Update trailing stop for long position.

        Parameters:
        -----------
        brick : pd.Series
            Current brick
        previous_brick : pd.Series
            Previous brick
        """
        if not self.config.stop_trail:
            return

        # Only trail if current brick is green and we're in profit
        if brick['color'] == 'GREEN' and brick['close'] > self.entry_price:
            # Stop trails to previous brick close (never goes down)
            self.stop_level = max(self.stop_level, previous_brick['close'])

    def update_trailing_stop_short(self, brick: pd.Series, previous_brick: pd.Series):
        """
        Update trailing stop for short position.

        Parameters:
        -----------
        brick : pd.Series
            Current brick
        previous_brick : pd.Series
            Previous brick
        """
        if not self.config.stop_trail:
            return

        # Only trail if current brick is red and we're in profit
        if brick['color'] == 'RED' and brick['close'] < self.entry_price:
            # Stop trails to previous brick close (never goes up)
            self.stop_level = min(self.stop_level, previous_brick['close'])

    def check_long_exit(self, brick: pd.Series) -> tuple[bool, str]:
        """
        Check if long position should be exited.

        Parameters:
        -----------
        brick : pd.Series
            Current brick

        Returns:
        --------
        tuple[bool, str]
            (should_exit, exit_reason)
        """
        # Check reverse brick exit
        if self.config.exit_on_reverse_brick and brick['color'] == 'RED':
            return True, "REVERSE_BRICK"

        # Check stop loss
        if brick['close'] <= self.stop_level:
            return True, "STOP_HIT"

        return False, ""

    def check_short_exit(self, brick: pd.Series) -> tuple[bool, str]:
        """
        Check if short position should be exited.

        Parameters:
        -----------
        brick : pd.Series
            Current brick

        Returns:
        --------
        tuple[bool, str]
            (should_exit, exit_reason)
        """
        # Check reverse brick exit
        if self.config.exit_on_reverse_brick and brick['color'] == 'GREEN':
            return True, "REVERSE_BRICK"

        # Check stop loss
        if brick['close'] >= self.stop_level:
            return True, "STOP_HIT"

        return False, ""

    def exit_position(self, brick: pd.Series, exit_reason: str):
        """
        Exit current position.

        Parameters:
        -----------
        brick : pd.Series
            Exit brick
        exit_reason : str
            Reason for exit
        """
        exit_price = brick['close']

        # Calculate P&L
        if self.position == 'LONG':
            pnl = (exit_price - self.entry_price) * self.position_size
            pnl_pct = ((exit_price / self.entry_price) - 1) * 100
        else:  # SHORT
            pnl = (self.entry_price - exit_price) * self.position_size
            pnl_pct = ((self.entry_price / exit_price) - 1) * 100

        # Update equity
        self.equity += pnl

        # Complete trade record
        self.current_trade.update({
            'exit_date': brick['datetime'],
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'exit_brick_number': brick['brick_number'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'duration_bricks': brick['brick_number'] - self.current_trade['entry_brick_number'],
            'equity_after': self.equity
        })

        self.trades.append(self.current_trade)

        # Reset position
        self.position = None
        self.entry_price = None
        self.stop_level = None
        self.position_size = 0
        self.current_trade = None

    def run(self, renko_df: pd.DataFrame, price_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Run strategy on Renko data.

        Parameters:
        -----------
        renko_df : pd.DataFrame
            Renko bricks DataFrame
        price_data : pd.DataFrame, optional
            Original price data for SMA calculation (if different from Renko)

        Returns:
        --------
        pd.DataFrame
            Renko DataFrame with strategy signals
        """
        # Calculate SMA (on original data if provided, otherwise on Renko)
        if price_data is not None and self.config.use_trend_filter:
            sma_values = self.calculate_sma(price_data['close'], self.config.trend_sma_period)
            # Align SMA with Renko bricks (use last available SMA value)
            renko_df['sma'] = renko_df['datetime'].map(
                lambda dt: sma_values[sma_values.index <= dt].iloc[-1] if any(sma_values.index <= dt) else np.nan
            )
        else:
            renko_df['sma'] = self.calculate_sma(renko_df['close'], self.config.trend_sma_period)

        # Initialize signal columns
        renko_df['signal'] = ''
        renko_df['position'] = ''
        renko_df['equity'] = self.config.initial_capital

        # Iterate through bricks
        for idx, brick in renko_df.iterrows():
            previous_brick = renko_df.loc[idx - 1] if idx > 0 else None
            sma_value = brick['sma']

            # Check for entries
            if self.position is None:
                if self.check_long_entry(brick, previous_brick, sma_value):
                    self.enter_long(brick, previous_brick)
                    renko_df.at[idx, 'signal'] = 'LONG_ENTRY'

                elif self.check_short_entry(brick, previous_brick, sma_value):
                    self.enter_short(brick, previous_brick)
                    renko_df.at[idx, 'signal'] = 'SHORT_ENTRY'

            # Check for exits
            elif self.position == 'LONG':
                # Update trailing stop
                if previous_brick is not None:
                    self.update_trailing_stop_long(brick, previous_brick)

                # Check exit
                should_exit, exit_reason = self.check_long_exit(brick)
                if should_exit:
                    self.exit_position(brick, exit_reason)
                    renko_df.at[idx, 'signal'] = f'LONG_EXIT_{exit_reason}'

            elif self.position == 'SHORT':
                # Update trailing stop
                if previous_brick is not None:
                    self.update_trailing_stop_short(brick, previous_brick)

                # Check exit
                should_exit, exit_reason = self.check_short_exit(brick)
                if should_exit:
                    self.exit_position(brick, exit_reason)
                    renko_df.at[idx, 'signal'] = f'SHORT_EXIT_{exit_reason}'

            # Record current position and equity
            renko_df.at[idx, 'position'] = self.position if self.position else 'FLAT'
            renko_df.at[idx, 'equity'] = self.equity

        return renko_df

    def get_trades_df(self) -> pd.DataFrame:
        """
        Get trades as DataFrame.

        Returns:
        --------
        pd.DataFrame
            Trades DataFrame
        """
        if not self.trades:
            return pd.DataFrame()

        return pd.DataFrame(self.trades)


if __name__ == "__main__":
    print("Renko Trend Following Strategy Module")
    print("======================================")
    print()
    print("This module implements the strategy logic.")
    print("Use with backtest.py for complete backtesting.")
