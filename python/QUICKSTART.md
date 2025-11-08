# Quick Start Guide - Python Version

Get up and running with the Renko Trend Following strategy in 5 minutes.

## Installation (2 minutes)

```bash
# Navigate to python directory
cd python

# Install dependencies
pip install -r requirements.txt

# That's it! You're ready to go.
```

## Your First Backtest (3 minutes)

### Option 1: Use the simple example (easiest)

```bash
python examples/simple_backtest.py
```

This will:
- ✓ Create sample data
- ✓ Run backtest with default settings
- ✓ Display performance report
- ✓ Show equity curve plot

### Option 2: Download real data and backtest

```bash
# Step 1: Download QQQ data (2010-2024)
python examples/download_data.py QQQ 2010-01-01 2024-12-31

# Step 2: Run backtest
python main.py --symbol QQQ --start 2010-01-01 --end 2024-12-31
```

Results will be saved to `outputs/QQQ_<timestamp>/`

### Option 3: Use your own data

```bash
# Your CSV should have: datetime, open, high, low, close, volume
python main.py --data /path/to/your/data.csv
```

## Understanding the Results

After running a backtest, you'll see:

```
PERFORMANCE REPORT
================================================================
Initial Capital:        $30,000.00
Final Equity:           $45,678.90
Total Return:           52.26%
CAGR:                   3.42%

TRADE STATISTICS
----------------------------------------------------------------
Total Trades:           24
Win Rate:               54.17%
Profit Factor:          2.15
Sharpe Ratio:           1.08

RISK METRICS
----------------------------------------------------------------
Max Drawdown:           -18.45%
Calmar Ratio:           0.19
```

**Key Metrics to Watch:**

✅ **Total Return**: Overall profit (aim for >50% over 5+ years)
✅ **Win Rate**: % of winning trades (40-60% is typical)
✅ **Profit Factor**: Gross profits / Gross losses (>1.5 is good)
✅ **Sharpe Ratio**: Risk-adjusted return (>0.8 is good)
✅ **Max Drawdown**: Worst peak-to-trough decline (<25% is good)

## Customizing Parameters

### Change Renko Brick Size

```bash
# Smaller bricks = more trades, more signals
python main.py --symbol QQQ --brick-size 0.008  # 0.8%

# Larger bricks = fewer trades, stronger trends
python main.py --symbol QQQ --brick-size 0.02   # 2.0%
```

**Rule of thumb:**
- Volatile stocks (TSLA, NVDA): 2-3%
- Index ETFs (QQQ, SPY): 0.8-1.5%
- Low volatility (GLD, utilities): 0.5-1.0%

### Change Trend Filter

```bash
# Shorter SMA = more trades
python main.py --symbol QQQ --sma-period 100

# Longer SMA = stronger trend filter
python main.py --symbol QQQ --sma-period 250

# Disable completely
python main.py --symbol QQQ --no-trend-filter
```

### Enable Short Positions

```bash
# Trade both directions
python main.py --symbol QQQ --allow-short

# Long-only (default, safer)
python main.py --symbol QQQ
```

### Adjust Position Sizing

```bash
# Conservative (70% of equity)
python main.py --symbol QQQ --position-size 0.70

# Aggressive (100% of equity)
python main.py --symbol QQQ --position-size 1.00
```

## Common Workflows

### 1. Test Different Symbols

```bash
# Technology
python main.py --symbol QQQ --brick-size 0.012

# Broad market
python main.py --symbol SPY --brick-size 0.010

# Gold
python main.py --symbol GLD --brick-size 0.008

# Individual stock
python main.py --symbol AAPL --brick-size 0.015
```

### 2. Quick Optimization

Test different brick sizes to find optimal:

```bash
for size in 0.008 0.010 0.012 0.015 0.020; do
  echo "Testing brick size: $size"
  python main.py --symbol QQQ --brick-size $size --no-plot
done
```

Compare Sharpe Ratios and choose best.

### 3. Compare to Buy-and-Hold

The report automatically shows:

```
COMPARISON TO BUY-AND-HOLD
----------------------------------------------------------------
Strategy Return:        52.26%
Buy-and-Hold Return:    312.45%
Outperformance:         -260.19%
```

If strategy underperforms, try:
- Adjusting brick size
- Changing SMA period
- Enabling shorts
- Different entry confirmation

## Interpreting the Plots

### Equity Curve (Blue line)

- **Smooth upward slope** = Good, consistent gains
- **Jagged with big drops** = High volatility, adjust risk
- **Flat periods** = Strategy not trading or breaking even

### Drawdown (Red area)

- **Deep red areas** = Periods of losses
- **Quick recovery** = Good, resilient strategy
- **Extended underwater** = May need optimization

### Trade Distribution (Histogram)

- **More green than red** = More winners than losers
- **Larger green bars** = Winners bigger than losers
- **Symmetric** = Equal win/loss distribution

## Troubleshooting

### "No trades generated"

**Cause:** Trend filter too restrictive

**Fix:**
```bash
python main.py --symbol QQQ --no-trend-filter
# OR
python main.py --symbol QQQ --sma-period 50
```

### "ImportError: No module named..."

**Fix:**
```bash
pip install -r requirements.txt
```

### "Can't download data"

**Fix:**
```bash
pip install yfinance
# OR use your own data
python main.py --data your_data.csv
```

### Plots not showing

**Fix:**
```bash
# Save to file instead
python main.py --symbol QQQ
# Plots saved to outputs/QQQ_*/
```

## Next Steps

1. ✅ **Run your first backtest** (you just did!)
2. 📊 **Experiment with parameters**
   - Try different brick sizes
   - Test different SMA periods
   - Compare symbols
3. 📈 **Optimize**
   - Use grid search (see README.md)
   - Run walk-forward analysis
4. 📚 **Learn more**
   - Read full documentation: `README.md`
   - Check presets: `../PRESETS.md`
   - Study code: `src/strategy.py`
5. 🧪 **Paper trade**
   - Test on recent data
   - Monitor performance
6. 🚀 **Go live** (only after thorough testing!)

## Recommended First Tests

### Conservative Strategy (Low Risk)

```bash
python main.py \
  --symbol SPY \
  --brick-size 0.010 \
  --sma-period 200 \
  --entry-confirm SECOND_GREEN \
  --position-size 0.70 \
  --start 2015-01-01
```

### Aggressive Strategy (Higher Risk/Reward)

```bash
python main.py \
  --symbol QQQ \
  --brick-size 0.015 \
  --sma-period 150 \
  --allow-short \
  --position-size 1.00 \
  --start 2015-01-01
```

### No Filter Strategy (Trade All Signals)

```bash
python main.py \
  --symbol QQQ \
  --brick-size 0.012 \
  --no-trend-filter \
  --entry-confirm FIRST_GREEN \
  --start 2015-01-01
```

## Getting Help

- **Full documentation**: See `README.md`
- **Code examples**: Check `examples/` directory
- **Strategy details**: See `../README.md` (main project)
- **Technical spec**: See original specification document

## Quick Reference Card

```bash
# Basic backtest
python main.py --symbol QQQ

# Custom brick size
--brick-size 0.015

# Change trend filter
--sma-period 150
--no-trend-filter

# Enable shorts
--allow-short

# Change confirmation
--entry-confirm SECOND_GREEN

# Adjust capital/size
--initial-capital 50000
--position-size 0.80

# Custom date range
--start 2015-01-01 --end 2024-12-31

# Use own data
--data my_data.csv

# Disable plots
--no-plot
```

---

**Ready to backtest?** Run `python examples/simple_backtest.py` now!

**Need help?** Check `README.md` for detailed documentation.

**Want presets?** See `../PRESETS.md` for tested configurations.
