import pandas as pd

from packages.quant.features import features


def scan(symbol: str, frame: pd.DataFrame) -> list[dict]:
    if len(frame) < 50:
        return []
    r = features(frame).iloc[-1]
    rules = {
        "momentum": [
            (r.close > r.sma50, "Close above SMA50"),
            (r.momentum20 > 0, "Positive 20-session momentum"),
            (r.macd > r.macd_signal, "MACD above signal"),
        ],
        "breakout": [
            (r.close > r.prior_high20, "Close above prior 20-session high"),
            (r.relative_volume > 1.5, "Relative volume above 1.5"),
            (r.sma20 > r.sma50, "SMA20 above SMA50"),
        ],
        "mean_reversion": [
            (r.rsi < 30, "RSI below 30"),
            (r.close < r.bollinger_lower, "Close below lower Bollinger band"),
            (r.close > r.sma50, "Longer trend remains positive"),
        ],
        "trend_following": [
            (r.close > r.sma20, "Close above SMA20"),
            (r.sma20 > r.sma50, "SMA20 above SMA50"),
            (r.momentum20 > 0, "Positive momentum"),
        ],
        "volume_expansion": [
            (r.relative_volume > 1.5, "Relative volume above 1.5"),
            (r.returns > 0, "Positive session return"),
            (r.close > r.sma20, "Close above SMA20"),
        ],
    }
    results = []
    for setup, checks in rules.items():
        # Require the defining first condition plus at least one corroboration.
        if not checks[0][0] or sum(bool(ok) for ok, _ in checks) < 2:
            continue
        risks = ["Earnings calendar unavailable", "Score is rule coverage, not probability"]
        if r.atr / r.close > 0.03:
            risks.append("ATR exceeds 3% of close")
        results.append(
            {
                "symbol": symbol,
                "setup": setup,
                "signal_strength": round(100 * sum(bool(x) for x, _ in checks) / 3, 2),
                "supporting_factors": [s for ok, s in checks if ok],
                "risk_factors": risks,
                "timestamp": str(r.timestamp),
            }
        )
    return results
