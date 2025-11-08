"""
Renko Trend Following Strategy - Python Implementation

This package provides a complete implementation of the Renko Trend Following
trading strategy with backtesting, optimization, and analysis tools.

Modules:
--------
- renko: Renko brick construction
- strategy: Trading strategy logic
- backtest: Backtesting engine
- metrics: Performance metrics

Example:
--------
>>> from backtest import Backtest, load_price_data
>>> from strategy import StrategyConfig
>>>
>>> data = load_price_data('data.csv')
>>> config = StrategyConfig()
>>> bt = Backtest(data, config, "PERCENTAGE", 0.01)
>>> bt.run()
>>> bt.print_report()

Version: 1.0.0
Author: Renko Trend Following Strategy
License: MIT
"""

__version__ = '1.0.0'
__author__ = 'Renko Trend Following Strategy'
__license__ = 'MIT'

from .renko import RenkoBuilder, build_renko_from_csv
from .strategy import RenkoTrendStrategy, StrategyConfig
from .backtest import Backtest, load_price_data
from .metrics import PerformanceMetrics, compare_to_buy_hold

__all__ = [
    'RenkoBuilder',
    'build_renko_from_csv',
    'RenkoTrendStrategy',
    'StrategyConfig',
    'Backtest',
    'load_price_data',
    'PerformanceMetrics',
    'compare_to_buy_hold',
]
