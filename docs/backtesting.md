# Backtesting semantics

## Scope and strategy interface

`Strategy.signals(frame)` returns one binary desired long/cash state for each bar. Included strategies are causal. Custom strategies are responsible for causality; returning a full vector does not make arbitrary user code safe. Tests alter future prices and assert earlier signals/equity do not change for each built-in strategy.

- SMA crossover: long if SMA20 > SMA50; else cash.
- RSI mean reversion: enter RSI14 < 30, remain until RSI14 > 55.
- Momentum: long if 20-session return > 0.
- Breakout: enter close above **previous** 20-session high; exit close below SMA20.

Start/end restrict both warm-up and measurement. There is no pre-start position. Strategies remain cash while required indicators are missing.

## Execution, sizing and costs

At bar t's open, execute the state computed at close[t−1]. No same-close fills. On entry:

```text
entry_price = open × (1 + slippage_bps/10000)
budget = cash × min(position_size, max_position_size)
quantity = budget / (entry_price × (1 + commission_bps/10000))
entry_fee = quantity × entry_price × commission_bps/10000
```

Shares are fractional; budget includes fees. No leverage, borrowing, shorts or pyramiding. Position caps constrain entry spend, not later mark-to-market drift. Exits sell the complete position with adverse slippage and an exit commission. Trade net P&L includes both commissions; slippage is embedded in fill prices. Cash does not earn interest.

Signal exits execute first at the open. For a remaining/new position, stop and target levels are percentages of slipped entry price. Gap-through fills use that session's open, then adverse exit slippage. Otherwise stop/target threshold prices are used with adverse slippage. If both thresholds are touched within the same daily candle, **stop wins**. This cannot reconstruct the true intraday path and must not be mistaken for a tick simulation. Targets are modeled as market-triggered exits, not guaranteed limit fills. A stopped position can re-enter on a later session if its prior-close target remains long, but never re-enters within the same bar.

The last position is marked at final close, **not forcibly liquidated**. Equity/return includes unrealized P&L; trade statistics include only completed trades. Terminal hypothetical liquidation costs are not included. Session timestamps label dates, not clock-time fills.

## Corporate actions

Yahoo's historical OHLC is split-adjusted, so a split must **not** be applied again to simulated research share units. No dividend cash is credited, and dividend-adjusted close is not mixed into OHLC fills. These are price-return simulations, including the SPY benchmark. Absolute simulated shares differ from contemporaneous unadjusted shares across future splits. This choice is useful for price-based baseline comparisons but is not a complete cash-account ledger or point-in-time dataset.

## Metrics

All ratios are fractions in JSON (0.1 means 10%). Undefined ratios are null, not infinity or invented zero.

- Total return: ending marked equity / initial capital − 1.
- CAGR / annualized return: `(ending/initial)^(365.25 / elapsed_calendar_days) − 1`. Same definition for both names. Very short windows can produce extreme annualization; overflow becomes null.
- Daily strategy returns: successive close equity ratios; initial point equals initial capital.
- Volatility: sample std of daily equity returns × sqrt(252).
- Sharpe: mean daily equity return / sample std × sqrt(252), zero risk-free rate.
- Sortino: mean daily return / RMS(min(daily return, 0)) × sqrt(252), zero target. Denominator includes all days.
- Maximum drawdown: minimum(equity / running peak − 1), negative-valued, includes initial capital.
- Win/loss rates: positive/negative net-P&L trades divided by all completed trades. Break-even trades count in the denominator but not either numerator.
- Average win/loss: conditional average trade dollar P&L; loss is negative.
- Profit factor: positive net P&L sum / absolute negative net P&L sum; undefined when there are no losses.
- Expectancy: mean net dollar P&L per completed trade.

A warning accompanies fewer than 30 completed trades or fewer than 252 bars. No confidence interval/significance claim is made before Phase 6. Serial correlation, fat tails and multiple testing are not resolved by a Sharpe calculation.

## Benchmark and provenance

SPY buy-and-hold enters the second available session open under the same fill-cost conventions, allocates full capital, disables stops/targets, and marks through the same final session. This intentionally does not pretend to invest at a first-bar close before a signal. It is not risk-matched to lower-allocation strategies. Exact session alignment is required; no forward-filled benchmark. Both asset and benchmark snapshots are saved with SHA-256 hashes.

`POST /runs/{id}/reproduce` recomputes using immutable compressed inputs and parameters, not current mutable bars. The result reports equality against saved metrics/curves/trades/position and benchmark metrics. Keep lockfiles and source revision with exported research. Changing methodology requires an engine version change.
