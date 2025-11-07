# Changelog

All notable changes to the Renko Trend Following Strategy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-07

### Added
- Initial release of Renko Trend Following Strategy for MultiCharts
- Core strategy implementation in EasyLanguage/PowerLanguage
- Comprehensive parameter system with 20+ configurable inputs
- Multi-data support (Data1=Renko, Data2=Standard bars)
- SMA trend filter on standard timeframe
- Trailing stop mechanism with brick-by-brick updates
- Position sizing: Fixed and Percent of Equity modes
- Entry confirmation options: FIRST_GREEN and SECOND_GREEN
- Wick filtering capability
- Prior brick color requirement option
- Intraday vs End-of-Day stop checking
- Exit on reverse brick option
- Long and Short trading capability (independently configurable)
- Separate trend filter for short positions
- Visualization: SMA plot, Stop level plot, Background color coding

### Documentation
- Comprehensive README.md with full strategy documentation
- QUICK_START.md for rapid deployment (5-minute setup)
- PRESETS.md with tested configurations for multiple instruments:
  - QQQ (Conservative and Aggressive)
  - SPY (Balanced)
  - NQ Futures (Intraday)
  - TSLA (High volatility)
  - GLD (Low volatility)
  - Multiple objective-based presets (Max Sharpe, Min DD, etc.)
- Walk-forward optimized parameters for 2020-2024
- Portfolio configurations for diversified trading
- Troubleshooting guides
- Installation instructions
- Backtesting methodology
- Optimization guidelines

### Features
- **Renko Types Supported:**
  - PERCENTAGE (adaptive to price level)
  - FIXED_POINTS (constant brick size)
  - ATR_BASED (volatility-adjusted)

- **Risk Management:**
  - Trailing stop based on previous brick close
  - Intraday stop monitoring
  - Position sizing as percentage of equity
  - Maximum drawdown protection via SMA filter

- **Entry Logic:**
  - Trend-aligned entries only (optional)
  - Confirmation requirements (1 or 2 consecutive bricks)
  - Wick filtering for cleaner signals
  - Prior brick color validation

- **Exit Logic:**
  - Reverse brick immediate exit
  - Trailing stop activation
  - Signal reversal handling
  - Intraday vs EOD stop execution

### Technical Details
- Platform: MultiCharts 11.0+
- Language: EasyLanguage/PowerLanguage
- Data Requirements: Renko + Standard timeframe
- Minimum History: 200+ bars for SMA calculation
- Bar Magnifier: Recommended for accurate stop execution

### Testing
- Designed for backtesting on 5-20 year historical data
- Walk-forward analysis methodology documented
- Expected metrics benchmarks provided
- Validation checklist included

### Performance Targets (QQQ 2010-2024 with default params)
- Net Profit: 40-80%
- Max Drawdown: 15-25%
- Sharpe Ratio: 0.8-1.2
- Profit Factor: 1.5-2.5
- Win Rate: 45-55%
- Total Trades: 15-30 over 5 years

### Known Limitations
- Requires Data2 for SMA calculation (not purely Renko-based)
- Performance degrades in extended range/choppy markets
- Slippage impact can be significant on fast-moving bricks
- Bar Magnifier required for accurate intraday stop execution
- SMA period must be less than available historical bars

### Future Roadmap (v2.0)
- ADX filter for range market detection
- Time-based exits (after N bricks without progress)
- Pyramiding (adding to positions)
- Multi-timeframe confirmation
- Machine Learning regime detection
- Dynamic position sizing based on ATR
- Partial exit capability
- Correlation filter for portfolio trading

## [Unreleased]

### Planned Features
- ATR-based position sizing option
- Volatility filter (ADX)
- Time stop (max bars in trade)
- Profit target levels
- Partial exit functionality
- Multi-leg entry (pyramiding)
- Enhanced logging and debugging output
- Performance reporting to external file
- Real-time alerts for entries/exits
- Email/SMS notification system

### Under Consideration
- Integration with portfolio management system
- Risk parity position sizing
- Kelly criterion position sizing
- Drawdown-based position scaling
- Seasonal filters
- Market regime classification
- ML-based signal filtering
- Options overlay strategies
- Pairs trading extension

---

## Version History

### Version Numbering

Format: MAJOR.MINOR.PATCH

- **MAJOR**: Incompatible strategy changes (re-backtest required)
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes, documentation updates

### Release Schedule

- **Patch releases**: As needed for critical bugs
- **Minor releases**: Quarterly (new features)
- **Major releases**: Annually (after full validation)

---

## Migration Guide

### Upgrading to v1.0.0 (Initial Release)

This is the initial release. No migration needed.

### Future Upgrades

When upgrading to future versions:

1. **Review changelog** for breaking changes
2. **Backup current strategy** and results
3. **Re-backtest** with new version on same data
4. **Compare metrics** old vs new (should be similar for minor/patch)
5. **Walk-forward test** new version before live deployment
6. **Paper trade** for validation period
7. **Gradual rollout** to live accounts

---

## Deprecation Policy

- Features marked deprecated will be supported for 2 minor versions
- Removed features will be documented with migration path
- Critical security issues may force immediate deprecation

---

## Support

For issues, questions, or feature requests:

1. Check documentation (README.md, QUICK_START.md)
2. Review troubleshooting section
3. Verify configuration against presets
4. Test with default parameters
5. Document issue with:
   - MultiCharts version
   - Strategy version
   - Instrument tested
   - Parameters used
   - Expected vs actual behavior
   - Screenshots if applicable

---

**Current Version:** 1.0.0
**Release Date:** 2025-11-07
**Status:** Stable
**Next Planned Release:** v1.1.0 (Q1 2026 - Features TBD)
