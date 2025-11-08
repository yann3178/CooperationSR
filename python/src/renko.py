"""
Renko Brick Construction Module

This module provides functionality to convert standard OHLC data into Renko bricks
with support for different brick sizing methods (PERCENTAGE, FIXED_POINTS, ATR_BASED).

Author: Renko Trend Following Strategy
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from typing import Literal, Optional


class RenkoBuilder:
    """
    Builds Renko bricks from OHLC data.

    Supports three brick sizing methods:
    - PERCENTAGE: Brick size as percentage of price
    - FIXED_POINTS: Fixed brick size in points
    - ATR_BASED: Brick size based on ATR
    """

    def __init__(
        self,
        brick_type: Literal["PERCENTAGE", "FIXED_POINTS", "ATR_BASED"] = "PERCENTAGE",
        brick_size: float = 0.01,
        atr_period: int = 14
    ):
        """
        Initialize RenkoBuilder.

        Parameters:
        -----------
        brick_type : str
            Type of brick sizing: "PERCENTAGE", "FIXED_POINTS", or "ATR_BASED"
        brick_size : float
            - If PERCENTAGE: percentage value (0.01 = 1%)
            - If FIXED_POINTS: fixed size in points
            - If ATR_BASED: ATR multiplier
        atr_period : int
            ATR period if using ATR_BASED
        """
        self.brick_type = brick_type
        self.brick_size = brick_size
        self.atr_period = atr_period

    def calculate_brick_size(self, price: float, atr: Optional[float] = None) -> float:
        """
        Calculate brick size based on configuration.

        Parameters:
        -----------
        price : float
            Current price level
        atr : float, optional
            ATR value (required if brick_type is ATR_BASED)

        Returns:
        --------
        float
            Calculated brick size
        """
        if self.brick_type == "PERCENTAGE":
            return price * self.brick_size
        elif self.brick_type == "FIXED_POINTS":
            return self.brick_size
        elif self.brick_type == "ATR_BASED":
            if atr is None:
                raise ValueError("ATR value required for ATR_BASED brick type")
            return atr * self.brick_size
        else:
            raise ValueError(f"Unknown brick type: {self.brick_type}")

    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Average True Range (ATR).

        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with 'high', 'low', 'close' columns
        period : int
            ATR period

        Returns:
        --------
        pd.Series
            ATR values
        """
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    def build_renko(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build Renko bricks from OHLC data.

        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with columns: 'datetime', 'open', 'high', 'low', 'close', 'volume'

        Returns:
        --------
        pd.DataFrame
            Renko bricks with columns:
            - datetime: timestamp of brick close
            - open: brick open price
            - high: brick high price
            - low: brick low price
            - close: brick close price
            - color: 'GREEN' or 'RED'
            - volume: cumulative volume
            - brick_number: sequential brick number
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty")

        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"DataFrame must contain columns: {required_cols}")

        # Calculate ATR if needed
        atr_values = None
        if self.brick_type == "ATR_BASED":
            atr_values = self.calculate_atr(df, self.atr_period)

        # Initialize
        bricks = []
        brick_number = 0

        # Start with first price
        current_brick_open = df.iloc[0]['close']
        atr_val = atr_values.iloc[self.atr_period] if atr_values is not None else None
        brick_size = self.calculate_brick_size(current_brick_open, atr_val)

        accumulated_volume = 0
        brick_start_time = df.index[0] if isinstance(df.index, pd.DatetimeIndex) else df.iloc[0].get('datetime', 0)

        # Iterate through price data
        for idx, row in df.iterrows():
            price = row['close']
            volume = row.get('volume', 0)
            accumulated_volume += volume

            # Update ATR if using ATR_BASED
            if self.brick_type == "ATR_BASED" and atr_values is not None:
                atr_val = atr_values.loc[idx]
                if not pd.isna(atr_val):
                    brick_size = self.calculate_brick_size(price, atr_val)
            elif self.brick_type == "PERCENTAGE":
                # Recalculate brick size based on current price level
                brick_size = self.calculate_brick_size(current_brick_open, None)

            # Check for brick formation
            while True:
                # Calculate potential brick close levels
                upper_brick_close = current_brick_open + brick_size
                lower_brick_close = current_brick_open - brick_size

                # Check if price moved enough to form a brick
                if price >= upper_brick_close:
                    # Form GREEN brick
                    brick = {
                        'datetime': idx if isinstance(df.index, pd.DatetimeIndex) else row.get('datetime', idx),
                        'open': current_brick_open,
                        'high': upper_brick_close,
                        'low': current_brick_open,
                        'close': upper_brick_close,
                        'color': 'GREEN',
                        'volume': accumulated_volume,
                        'brick_number': brick_number
                    }
                    bricks.append(brick)
                    brick_number += 1

                    # Update for next brick
                    current_brick_open = upper_brick_close
                    accumulated_volume = 0
                    brick_start_time = idx if isinstance(df.index, pd.DatetimeIndex) else row.get('datetime', idx)

                elif price <= lower_brick_close:
                    # Form RED brick
                    brick = {
                        'datetime': idx if isinstance(df.index, pd.DatetimeIndex) else row.get('datetime', idx),
                        'open': current_brick_open,
                        'high': current_brick_open,
                        'low': lower_brick_close,
                        'close': lower_brick_close,
                        'color': 'RED',
                        'volume': accumulated_volume,
                        'brick_number': brick_number
                    }
                    bricks.append(brick)
                    brick_number += 1

                    # Update for next brick
                    current_brick_open = lower_brick_close
                    accumulated_volume = 0
                    brick_start_time = idx if isinstance(df.index, pd.DatetimeIndex) else row.get('datetime', idx)

                else:
                    # No brick formed, continue
                    break

        # Create DataFrame from bricks
        if not bricks:
            raise ValueError("No Renko bricks were formed. Try adjusting brick size.")

        renko_df = pd.DataFrame(bricks)

        # Add additional useful columns
        renko_df['previous_color'] = renko_df['color'].shift(1)
        renko_df['has_lower_wick'] = False  # Pure Renko has no wicks
        renko_df['has_upper_wick'] = False  # Pure Renko has no wicks

        # Count consecutive bricks
        renko_df['consecutive_same_color'] = self._count_consecutive_colors(renko_df)

        return renko_df

    def _count_consecutive_colors(self, renko_df: pd.DataFrame) -> pd.Series:
        """
        Count consecutive bricks of the same color.

        Parameters:
        -----------
        renko_df : pd.DataFrame
            Renko bricks DataFrame

        Returns:
        --------
        pd.Series
            Count of consecutive same-color bricks
        """
        consecutive = []
        count = 0
        prev_color = None

        for color in renko_df['color']:
            if color == prev_color:
                count += 1
            else:
                count = 1
            consecutive.append(count)
            prev_color = color

        return pd.Series(consecutive, index=renko_df.index)


def build_renko_from_csv(
    filepath: str,
    brick_type: str = "PERCENTAGE",
    brick_size: float = 0.01,
    atr_period: int = 14
) -> pd.DataFrame:
    """
    Convenience function to build Renko from CSV file.

    Parameters:
    -----------
    filepath : str
        Path to CSV file with OHLC data
    brick_type : str
        Type of brick sizing
    brick_size : float
        Brick size parameter
    atr_period : int
        ATR period

    Returns:
    --------
    pd.DataFrame
        Renko bricks DataFrame
    """
    # Read CSV
    df = pd.read_csv(filepath)

    # Try to parse datetime column
    datetime_cols = ['datetime', 'date', 'timestamp', 'time']
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
            df.set_index(col, inplace=True)
            break

    # Standardize column names (handle different cases)
    column_mapping = {}
    for col in df.columns:
        lower_col = col.lower()
        if lower_col in ['open', 'high', 'low', 'close', 'volume']:
            column_mapping[col] = lower_col

    df.rename(columns=column_mapping, inplace=True)

    # Build Renko
    builder = RenkoBuilder(brick_type, brick_size, atr_period)
    renko_df = builder.build_renko(df)

    return renko_df


if __name__ == "__main__":
    # Example usage
    print("Renko Builder Module")
    print("====================")
    print()
    print("Example: Building Renko bricks")

    # Create sample data
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    np.random.seed(42)

    # Simulate price data with trend
    prices = 100 + np.cumsum(np.random.randn(100) * 2)

    sample_data = pd.DataFrame({
        'datetime': dates,
        'open': prices + np.random.randn(100) * 0.5,
        'high': prices + np.abs(np.random.randn(100) * 1.5),
        'low': prices - np.abs(np.random.randn(100) * 1.5),
        'close': prices,
        'volume': np.random.randint(1000, 10000, 100)
    })

    sample_data.set_index('datetime', inplace=True)

    # Build Renko bricks
    builder = RenkoBuilder(brick_type="PERCENTAGE", brick_size=0.02)
    renko = builder.build_renko(sample_data)

    print(f"Input data: {len(sample_data)} bars")
    print(f"Renko bricks: {len(renko)} bricks")
    print()
    print("First 5 bricks:")
    print(renko.head())
    print()
    print("Color distribution:")
    print(renko['color'].value_counts())
