"""
Basic tests for Renko Trend Following Strategy

Run with: pytest tests/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import numpy as np
import pytest

from renko import RenkoBuilder
from strategy import RenkoTrendStrategy, StrategyConfig
from metrics import PerformanceMetrics


def create_sample_data(n_bars=100):
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=n_bars, freq='D')

    prices = 100 + np.cumsum(np.random.randn(n_bars) * 2)

    df = pd.DataFrame({
        'open': prices + np.random.randn(n_bars) * 0.5,
        'high': prices + np.abs(np.random.randn(n_bars) * 1.5),
        'low': prices - np.abs(np.random.randn(n_bars) * 1.5),
        'close': prices,
        'volume': np.random.randint(1000, 10000, n_bars)
    }, index=dates)

    return df


class TestRenkoBuilder:
    """Tests for RenkoBuilder class."""

    def test_percentage_renko(self):
        """Test percentage-based Renko construction."""
        data = create_sample_data(100)
        builder = RenkoBuilder("PERCENTAGE", 0.02)

        renko = builder.build_renko(data)

        assert len(renko) > 0, "Should create at least one brick"
        assert 'color' in renko.columns
        assert all(renko['color'].isin(['GREEN', 'RED']))

    def test_fixed_renko(self):
        """Test fixed-point Renko construction."""
        data = create_sample_data(100)
        builder = RenkoBuilder("FIXED_POINTS", 5.0)

        renko = builder.build_renko(data)

        assert len(renko) > 0
        assert 'brick_number' in renko.columns

    def test_brick_size_calculation(self):
        """Test brick size calculation methods."""
        builder = RenkoBuilder("PERCENTAGE", 0.01)

        # Test percentage
        size = builder.calculate_brick_size(100.0)
        assert size == 1.0, "1% of 100 should be 1.0"

        # Test fixed
        builder.brick_type = "FIXED_POINTS"
        builder.brick_size = 10.0
        size = builder.calculate_brick_size(100.0)
        assert size == 10.0

        # Test ATR
        builder.brick_type = "ATR_BASED"
        builder.brick_size = 2.0
        size = builder.calculate_brick_size(100.0, atr=5.0)
        assert size == 10.0, "2.0 * 5.0 ATR should be 10.0"


class TestStrategy:
    """Tests for RenkoTrendStrategy class."""

    def test_strategy_initialization(self):
        """Test strategy initialization."""
        config = StrategyConfig()
        strategy = RenkoTrendStrategy(config)

        assert strategy.position is None
        assert strategy.equity == config.initial_capital

    def test_long_entry_conditions(self):
        """Test long entry condition logic."""
        config = StrategyConfig(
            allow_long=True,
            use_trend_filter=False
        )
        strategy = RenkoTrendStrategy(config)

        # Create mock brick data
        brick = pd.Series({
            'color': 'GREEN',
            'close': 105.0,
            'consecutive_same_color': 1,
            'has_lower_wick': False,
            'brick_number': 5,
            'datetime': pd.Timestamp('2020-01-05')
        })

        previous_brick = pd.Series({
            'color': 'RED',
            'close': 100.0
        })

        # Should allow long entry
        can_enter = strategy.check_long_entry(brick, previous_brick, 100.0)
        assert can_enter is True

    def test_position_sizing(self):
        """Test position sizing calculation."""
        config = StrategyConfig(
            position_size_type="PERCENT_EQUITY",
            position_size_value=0.50,
            initial_capital=10000
        )
        strategy = RenkoTrendStrategy(config)
        strategy.equity = 10000

        shares = strategy.calculate_position_size(100.0)
        assert shares == 50, "50% of 10000 at $100/share = 50 shares"

    def test_trailing_stop(self):
        """Test trailing stop logic."""
        config = StrategyConfig(stop_trail=True)
        strategy = RenkoTrendStrategy(config)

        # Simulate entry
        strategy.position = 'LONG'
        strategy.entry_price = 100.0
        strategy.stop_level = 98.0

        # Create advancing brick
        brick = pd.Series({
            'color': 'GREEN',
            'close': 105.0
        })
        previous_brick = pd.Series({
            'close': 103.0
        })

        # Update trailing stop
        strategy.update_trailing_stop_long(brick, previous_brick)

        # Stop should have moved up
        assert strategy.stop_level > 98.0


class TestMetrics:
    """Tests for PerformanceMetrics class."""

    def test_metrics_calculation(self):
        """Test basic metrics calculations."""
        # Create sample trades
        trades = pd.DataFrame({
            'pnl': [100, -50, 150, -30, 200],
            'pnl_pct': [10, -5, 15, -3, 20],
            'entry_date': pd.date_range('2020-01-01', periods=5, freq='10D'),
            'exit_date': pd.date_range('2020-01-05', periods=5, freq='10D'),
        })

        # Create equity curve
        equity = pd.Series(
            [10000, 10100, 10050, 10200, 10170, 10370],
            index=pd.date_range('2020-01-01', periods=6, freq='10D')
        )

        metrics = PerformanceMetrics(trades, equity, 10000)

        # Test calculations
        assert metrics.total_trades() == 5
        assert metrics.winning_trades() == 3
        assert metrics.losing_trades() == 2
        assert metrics.win_rate() == 60.0

        total_return = metrics.total_return()
        assert total_return > 0

        profit_factor = metrics.profit_factor()
        assert profit_factor > 1.0  # More profits than losses

    def test_empty_metrics(self):
        """Test metrics with no trades."""
        trades = pd.DataFrame()
        equity = pd.Series([10000], index=pd.date_range('2020-01-01', periods=1))

        metrics = PerformanceMetrics(trades, equity, 10000)

        assert metrics.total_trades() == 0
        assert metrics.win_rate() == 0.0
        assert metrics.profit_factor() == 0.0


def test_end_to_end():
    """Test complete backtest workflow."""
    # Create data
    data = create_sample_data(200)

    # Build Renko
    builder = RenkoBuilder("PERCENTAGE", 0.02)
    renko = builder.build_renko(data)

    assert len(renko) > 0, "Should create Renko bricks"

    # Run strategy
    config = StrategyConfig(
        use_trend_filter=False,  # Disable for test
        initial_capital=10000
    )
    strategy = RenkoTrendStrategy(config)
    results = strategy.run(renko)

    assert len(results) == len(renko)
    assert 'equity' in results.columns

    # Check if trades were made (not guaranteed with random data)
    # Just verify the structure works
    trades = strategy.get_trades_df()
    assert isinstance(trades, pd.DataFrame)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
