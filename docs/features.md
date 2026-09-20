# Feature and scanner formulas

All features use completed split-adjusted daily OHLC, exclude dividends and are causal. No centered windows or forward fill are used. Undefined/warm-up values remain NaN internally and null in the API. Substituting a future price cannot alter an earlier feature, which is regression tested.

| Feature | Definition / convention |
| --- | --- |
| Simple return | `close[t] / close[t-1] - 1` |
| Log return | `ln(close[t] / close[t-1])` |
| SMA20 / SMA50 | Simple mean over 20/50 closes; full window required |
| EMA20 | Recursive exponential mean, alpha `2/21`, seeded by first close; first 19 outputs suppressed |
| RSI14 | Wilder-smoothed gains/losses, seeded by first 14 deltas; `100 - 100/(1+gain/loss)`; all gains=100, flat=50 |
| MACD | EMA12 − EMA26; signal EMA9 of MACD; histogram MACD − signal |
| ATR14 | Wilder average of `max(high-low, abs(high-prev_close), abs(low-prev_close))`; first bar uses high-low |
| Bollinger bands | SMA20 ± 2 × population standard deviation of last 20 closes |
| Rolling volatility | Sample std of last 20 simple returns × sqrt(252) |
| Volume SMA20 | Mean volume of the last 20 sessions including current |
| Relative volume | Current volume / mean of **previous** 20 sessions; zero denominator → null |
| Rolling high/low | Highest high / lowest low in last 20 sessions including current |
| Prior high20 | Highest high in previous 20 sessions, excludes current bar |
| Drawdown | Close / cumulative maximum close − 1, since beginning of provided history |
| Momentum20 | Close / close 20 sessions ago − 1 |
| Distance to SMA | Close / SMA − 1 |
| Daily VWAP proxy20 | Sum(typical price × daily volume) / sum(volume), 20 sessions; typical=(high+low+close)/3 |

The VWAP proxy is **not** intraday VWAP or a realistic execution price. Its explicit name prevents that interpretation.

## Deterministic scanner

Each setup has three equally weighted boolean rules. Signal strength = `100 × satisfied rules / 3`, rounded to two decimals. A candidate must satisfy its defining first rule and at least one other rule. It measures rule coverage, **not predictive confidence**, and has no claimed historical success rate. At least 50 bars are required.

| Setup | Defining rule | Supporting rule 2 | Supporting rule 3 |
| --- | --- | --- | --- |
| Momentum | Close > SMA50 | Momentum20 > 0 | MACD > signal |
| Breakout | Close > prior high20 | Relative volume > 1.5 | SMA20 > SMA50 |
| Mean reversion | RSI < 30 | Close < lower Bollinger band | Close > SMA50 |
| Trend following | Close > SMA20 | SMA20 > SMA50 | Momentum20 > 0 |
| Volume expansion | Relative volume > 1.5 | Session return > 0 | Close > SMA20 |

Each result includes symbol, setup, rule coverage, the satisfied factors, timestamp and limitations. ATR/close above 3% adds a volatility warning. Earnings timing is **unavailable**, never invented. Phase 6 should attach properly isolated historical event-study distributions; until then the scanner does not imply backtested statistical significance.
