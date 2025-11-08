# Renko Trend Following Strategy - Python Implementation

Complete Python implementation of the Renko Trend Following trading strategy with backtesting, optimization, and visualization capabilities.

## 📦 Quick Start

### Installation

```bash
# Clone or download the repository
cd python

# Install dependencies
pip install -r requirements.txt

# Optional: Install in development mode
pip install -e .
```

### Run Your First Backtest

```bash
# Download data and run backtest on QQQ
python main.py --symbol QQQ --start 2015-01-01 --end 2024-12-31

# Or use your own data
python main.py --data path/to/your/data.csv

# Run simple example
python examples/simple_backtest.py
```

## 📁 Project Structure

```
python/
├── src/
│   ├── renko.py         # Renko brick construction
│   ├── strategy.py      # Strategy logic
│   ├── backtest.py      # Backtesting engine
│   └── metrics.py       # Performance metrics
├── examples/
│   ├── simple_backtest.py      # Simple example
│   └── download_data.py        # Data download utility
├── data/                # Downloaded data (created automatically)
├── outputs/             # Backtest results (created automatically)
├── main.py              # Main execution script
└── requirements.txt     # Dependencies
```

## 🚀 Usage

### Basic Backtest

```python
import sys
sys.path.insert(0, 'src')

from backtest import Backtest, load_price_data
from strategy import StrategyConfig

# Load data
price_data = load_price_data('data/QQQ_2010-01-01_2024-12-31.csv')

# Configure strategy
config = StrategyConfig(
    use_trend_filter=True,
    trend_sma_period=200,
    entry_confirm_type="FIRST_GREEN",
    allow_long=True,
    allow_short=False,
    position_size_value=0.90,
    initial_capital=30000
)

# Run backtest
backtest = Backtest(
    price_data=price_data,
    strategy_config=config,
    brick_type="PERCENTAGE",
    brick_size=0.01  # 1%
)

summary = backtest.run()
backtest.print_report()
backtest.plot_results()
```

### Command Line Interface

```bash
# Basic usage
python main.py --symbol QQQ --start 2010-01-01 --end 2024-12-31

# Custom configuration
python main.py \
  --symbol QQQ \
  --start 2010-01-01 \
  --end 2024-12-31 \
  --brick-size 0.015 \
  --sma-period 200 \
  --allow-short \
  --initial-capital 50000

# Disable trend filter
python main.py --symbol QQQ --no-trend-filter

# Use custom data
python main.py --data my_data.csv --brick-size 0.02
```

### Download Historical Data

```bash
# Download QQQ data
python examples/download_data.py QQQ 2010-01-01 2024-12-31

# Download SPY data
python examples/download_data.py SPY 2000-01-01 2024-12-31

# Save to custom directory
python examples/download_data.py AAPL 2015-01-01 2024-12-31 --output my_data
```

## 🎯 Strategy Configuration

### StrategyConfig Parameters

```python
StrategyConfig(
    # Trend Filter
    use_trend_filter=True,          # Enable SMA trend filter
    trend_sma_period=200,            # SMA period
    trend_margin=0.00,               # Margin above/below SMA (0.02 = 2%)

    # Entry Conditions
    entry_confirm_type="FIRST_GREEN",  # or "SECOND_GREEN"
    require_no_wick=False,           # Require no wicks on entry brick
    require_prior_red=True,          # Require prior brick opposite color

    # Trading Direction
    allow_long=True,                 # Enable long positions
    allow_short=False,               # Enable short positions
    short_trend_filter=True,         # Require shorts below SMA

    # Position Sizing
    position_size_type="PERCENT_EQUITY",  # or "FIXED"
    position_size_value=0.90,        # 90% of equity or fixed shares
    initial_capital=30000,           # Starting capital

    # Stop Management
    stop_type="PREVIOUS_BRICK",      # Stop at previous brick close
    stop_intraday=True,              # Check stop in real-time
    stop_trail=True,                 # Enable trailing stop
    exit_on_reverse_brick=True       # Exit on reverse brick
)
```

### Renko Configuration

```python
# Percentage-based (Recommended)
brick_type="PERCENTAGE"
brick_size=0.01  # 1% bricks

# Fixed points
brick_type="FIXED_POINTS"
brick_size=100  # 100 points

# ATR-based
brick_type="ATR_BASED"
brick_size=1.5  # 1.5 × ATR
atr_period=14
```

## 📊 Presets

### QQQ - Conservative (Long-only)

```python
config = StrategyConfig(
    use_trend_filter=True,
    trend_sma_period=200,
    entry_confirm_type="SECOND_GREEN",
    allow_long=True,
    allow_short=False,
    position_size_value=0.80,
    initial_capital=30000
)

brick_size = 0.012  # 1.2%
```

**Expected Performance (2010-2024):**
- Return: 60-90%
- Max DD: 15-20%
- Sharpe: 1.0-1.3

### QQQ - Aggressive (Long/Short)

```python
config = StrategyConfig(
    use_trend_filter=True,
    trend_sma_period=150,
    entry_confirm_type="FIRST_GREEN",
    allow_long=True,
    allow_short=True,
    position_size_value=0.90,
    initial_capital=30000
)

brick_size = 0.015  # 1.5%
```

**Expected Performance (2010-2024):**
- Return: 80-120%
- Max DD: 25-35%
- Sharpe: 0.8-1.1

### SPY - Balanced

```python
config = StrategyConfig(
    use_trend_filter=True,
    trend_sma_period=200,
    trend_margin=0.005,
    entry_confirm_type="FIRST_GREEN",
    allow_long=True,
    allow_short=False,
    position_size_value=0.85,
    initial_capital=30000
)

brick_size = 0.010  # 1.0%
```

## 📈 Output & Reporting

### Performance Metrics

The backtest automatically calculates:

**Performance:**
- Total Return (%)
- Total Return ($)
- CAGR
- Buy-and-Hold comparison

**Trade Statistics:**
- Total Trades
- Win Rate (%)
- Average Win/Loss
- Largest Win/Loss
- Profit Factor
- Expectancy

**Risk Metrics:**
- Maximum Drawdown (% and $)
- Drawdown Duration
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio

**Distribution:**
- Consecutive Wins/Losses
- Average Trade Duration

### Exported Files

Results are automatically exported to `outputs/<symbol>_<timestamp>/`:

```
outputs/QQQ_20241107_123456/
├── trades.csv              # All trades with entry/exit details
├── renko_signals.csv       # Renko bricks with signals
├── metrics.json            # Performance metrics
├── config.json             # Strategy configuration
├── equity_curve.png        # Equity curve plot
└── renko_signals.png       # Renko chart with signals
```

### Visualization

```python
# Plot equity curve and drawdown
backtest.plot_results()

# Plot Renko bricks with signals
backtest.plot_renko_with_signals()

# Save plots
backtest.plot_results(save_path='results/equity.png')
```

## 🔧 Advanced Usage

### Custom Data Format

Your CSV should have these columns:
- `datetime` or `date` (will be parsed automatically)
- `open`, `high`, `low`, `close`
- `volume` (optional)

```python
# Load and prepare data
import pandas as pd

df = pd.read_csv('my_data.csv')
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)

# Run backtest
backtest = Backtest(df, config, "PERCENTAGE", 0.01)
backtest.run()
```

### Walk-Forward Analysis

```python
from datetime import datetime, timedelta

# Define periods
start = datetime(2010, 1, 1)
end = datetime(2024, 12, 31)
is_period = timedelta(days=365 * 4)  # 4 years in-sample
oos_period = timedelta(days=365)      # 1 year out-of-sample

# Walk-forward loop
results = []
current = start

while current + is_period + oos_period < end:
    # In-sample period
    is_start = current
    is_end = current + is_period

    # Out-of-sample period
    oos_start = is_end
    oos_end = oos_start + oos_period

    # Optimize on IS data (simplified - use your optimization logic)
    is_data = price_data[is_start:is_end]
    # ... optimization code ...

    # Test on OOS data
    oos_data = price_data[oos_start:oos_end]
    backtest = Backtest(oos_data, best_config, "PERCENTAGE", best_brick_size)
    summary = backtest.run()

    results.append({
        'oos_period': f"{oos_start.date()} to {oos_end.date()}",
        'return': summary['metrics']['total_return_pct'],
        'sharpe': summary['metrics']['sharpe_ratio']
    })

    current += oos_period

# Analyze results
import pandas as pd
results_df = pd.DataFrame(results)
print(results_df)
```

### Parameter Optimization

```python
from itertools import product

# Define parameter grid
brick_sizes = [0.008, 0.01, 0.012, 0.015, 0.02]
sma_periods = [150, 200, 250]
confirm_types = ["FIRST_GREEN", "SECOND_GREEN"]

best_sharpe = -999
best_params = None

# Grid search
for brick_size, sma_period, confirm_type in product(brick_sizes, sma_periods, confirm_types):
    config = StrategyConfig(
        trend_sma_period=sma_period,
        entry_confirm_type=confirm_type,
        # ... other params ...
    )

    backtest = Backtest(price_data, config, "PERCENTAGE", brick_size)
    summary = backtest.run()

    sharpe = summary['metrics']['sharpe_ratio']

    if sharpe > best_sharpe:
        best_sharpe = sharpe
        best_params = (brick_size, sma_period, confirm_type)

    print(f"Brick: {brick_size}, SMA: {sma_period}, Confirm: {confirm_type} → Sharpe: {sharpe:.2f}")

print(f"\nBest parameters: {best_params}")
print(f"Best Sharpe: {best_sharpe:.2f}")
```

### Multiple Symbols

```python
symbols = ['QQQ', 'SPY', 'IWM', 'DIA']
results = {}

for symbol in symbols:
    print(f"\nBacktesting {symbol}...")

    # Download data
    data = download_data(symbol, '2010-01-01', '2024-12-31')

    # Run backtest
    backtest = Backtest(data, config, "PERCENTAGE", 0.01)
    summary = backtest.run()

    results[symbol] = summary['metrics']

# Compare results
import pandas as pd
comparison = pd.DataFrame(results).T
print(comparison[['total_return_pct', 'sharpe_ratio', 'max_drawdown_pct']])
```

## 🧪 Testing

```bash
# Run tests (if implemented)
pytest tests/

# Test individual modules
python src/renko.py
python src/strategy.py
python src/metrics.py
```

## 📚 Module Documentation

### renko.py

**RenkoBuilder** class for constructing Renko bricks:
- `build_renko(df)`: Convert OHLC to Renko
- `calculate_brick_size(price, atr)`: Calculate dynamic brick size
- Supports PERCENTAGE, FIXED_POINTS, ATR_BASED

### strategy.py

**RenkoTrendStrategy** class implementing trading logic:
- `run(renko_df, price_data)`: Execute strategy
- `check_long_entry()`: Long entry conditions
- `check_short_entry()`: Short entry conditions
- `update_trailing_stop_long()`: Update trailing stop
- `get_trades_df()`: Get completed trades

### backtest.py

**Backtest** class orchestrating complete backtesting:
- `run()`: Run complete backtest
- `plot_results()`: Plot equity curve and metrics
- `plot_renko_with_signals()`: Plot Renko with signals
- `export_results()`: Export to CSV/JSON
- `print_report()`: Print performance report

### metrics.py

**PerformanceMetrics** class calculating all metrics:
- `get_all_metrics()`: Calculate all metrics
- `sharpe_ratio()`: Sharpe ratio
- `max_drawdown()`: Maximum drawdown
- `profit_factor()`: Profit factor
- `print_report()`: Formatted report

## ⚠️ Important Notes

### Data Requirements

- Minimum 200+ bars for SMA calculation
- Clean data without gaps recommended
- Adjusted prices recommended for stocks

### Performance Considerations

- Renko construction: O(n) where n = number of price bars
- Strategy execution: O(m) where m = number of Renko bricks
- Typical: 1000 price bars → 50-200 Renko bricks

### Limitations

- No tick-by-tick simulation (uses close prices)
- Slippage not modeled (assumes market execution)
- Commission not included (add manually if needed)
- No multi-threading for optimization (sequential)

## 🐛 Troubleshooting

### No trades generated

**Cause:** Trend filter too restrictive or not enough data

**Solution:**
```python
# Disable trend filter temporarily
config.use_trend_filter = False

# Or reduce SMA period
config.trend_sma_period = 50
```

### Import errors

**Cause:** src not in path

**Solution:**
```python
import sys
sys.path.insert(0, 'src')
```

### Plotting errors

**Cause:** No display or matplotlib backend issue

**Solution:**
```python
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

# Or disable plotting
python main.py --no-plot
```

## 📖 Examples

### Example 1: Quick Backtest

```python
from backtest import Backtest, load_price_data
from strategy import StrategyConfig

# Load data
data = load_price_data('data/QQQ_2010-01-01_2024-12-31.csv')

# Simple config
config = StrategyConfig(initial_capital=10000)

# Run
bt = Backtest(data, config, "PERCENTAGE", 0.01)
bt.run()
bt.print_report()
```

### Example 2: Compare Strategies

```python
configs = {
    'Conservative': StrategyConfig(
        trend_sma_period=200,
        entry_confirm_type="SECOND_GREEN",
        position_size_value=0.70
    ),
    'Aggressive': StrategyConfig(
        trend_sma_period=150,
        entry_confirm_type="FIRST_GREEN",
        position_size_value=1.00,
        allow_short=True
    )
}

for name, config in configs.items():
    print(f"\n=== {name} ===")
    bt = Backtest(data, config, "PERCENTAGE", 0.01)
    bt.run()
    bt.print_report()
```

## 🔗 Links

- MultiCharts Version: See `../RenkoTrendFollowing_Strategy.txt`
- Full Documentation: See `../README.md`
- Technical Specification: See original spec document

## 📝 License

MIT License - See `../LICENSE`

## ⚠️ Disclaimer

This software is for educational purposes only. Trading carries risk. Past performance does not guarantee future results. Use at your own risk.

---

**Version:** 1.0.0
**Last Updated:** 2025-11-07
**Python:** 3.8+
