"""Vectorized technical indicators computed using pandas and numpy."""
import numpy as np
import pandas as pd


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average (EMA)."""
    return series.ewm(span=period, adjust=False).mean()


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculates Simple Moving Average (SMA)."""
    return series.rolling(window=period, min_periods=period).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI) using Wilder's smoothing."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's exponential smoothing: alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Average True Range (ATR)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    if not true_range.empty:
        true_range.iloc[0] = tr1.iloc[0]
    # Wilder's smoothing
    atr = true_range.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr


def compute_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    std_dev: float = 2.0
) -> pd.DataFrame:
    """Calculates Bollinger Bands: middle, upper, lower, bandwidth, and %B."""
    middle = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    bandwidth = (upper - lower) / middle.replace(0, np.nan)

    return pd.DataFrame({
        "bb_middle": middle,
        "bb_upper": upper,
        "bb_lower": lower,
        "bb_bandwidth": bandwidth
    }, index=close.index)


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.DataFrame:
    """Calculates Average Directional Index (ADX), +DI, and -DI."""
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    tr_smoothed = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    plus_dm_smoothed = pd.Series(plus_dm, index=high.index).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    minus_dm_smoothed = pd.Series(minus_dm, index=high.index).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    plus_di = 100.0 * (plus_dm_smoothed / tr_smoothed.replace(0, np.nan))
    minus_di = 100.0 * (minus_dm_smoothed / tr_smoothed.replace(0, np.nan))

    di_sum = plus_di + minus_di
    dx = 100.0 * ((plus_di - minus_di).abs() / di_sum.replace(0, np.nan))
    adx = dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    return pd.DataFrame({
        "adx": adx.fillna(0.0),
        "plus_di": plus_di.fillna(0.0),
        "minus_di": minus_di.fillna(0.0)
    }, index=high.index)


def compute_macd(
    close: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> pd.DataFrame:
    """Calculates Moving Average Convergence Divergence (MACD)."""
    ema_fast = compute_ema(close, fast_period)
    ema_slow = compute_ema(close, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    return pd.DataFrame({
        "macd_line": macd_line,
        "macd_signal": signal_line,
        "macd_hist": histogram
    }, index=close.index)


def compute_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0
) -> pd.DataFrame:
    """Calculates Supertrend indicator with upper/lower bands and trend direction (1 = Bullish, -1 = Bearish)."""
    atr = compute_atr(high, low, close, period)
    hl2 = (high + low) / 2.0

    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    n = len(close)
    final_upper = basic_upper.values.copy()
    final_lower = basic_lower.values.copy()
    trend = np.ones(n, dtype=int)
    supertrend = np.zeros(n, dtype=float)

    c_vals = close.values

    for i in range(1, n):
        # Final lower band
        if basic_lower.iloc[i] > final_lower[i - 1] or c_vals[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower.iloc[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Final upper band
        if basic_upper.iloc[i] < final_upper[i - 1] or c_vals[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper.iloc[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Trend direction
        if trend[i - 1] == 1:
            if c_vals[i] < final_lower[i]:
                trend[i] = -1
                supertrend[i] = final_upper[i]
            else:
                trend[i] = 1
                supertrend[i] = final_lower[i]
        else:
            if c_vals[i] > final_upper[i]:
                trend[i] = 1
                supertrend[i] = final_lower[i]
            else:
                trend[i] = -1
                supertrend[i] = final_upper[i]

    if n > 0:
        supertrend[0] = final_lower[0]

    return pd.DataFrame({
        "supertrend": supertrend,
        "supertrend_direction": trend,
        "supertrend_upper": final_upper,
        "supertrend_lower": final_lower
    }, index=close.index)


def compute_donchian_channels(
    high: pd.Series,
    low: pd.Series,
    period: int = 20
) -> pd.DataFrame:
    """Calculates Donchian Channels (highest high, lowest low, and midline)."""
    upper = high.rolling(window=period, min_periods=period).max()
    lower = low.rolling(window=period, min_periods=period).min()
    middle = (upper + lower) / 2.0

    return pd.DataFrame({
        "donchian_upper": upper.bfill(),
        "donchian_lower": lower.bfill(),
        "donchian_middle": middle.bfill()
    }, index=high.index)


def compute_keltner_channels(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 1.5
) -> pd.DataFrame:
    """Calculates Keltner Channels based on EMA and ATR."""
    middle = compute_ema(close, ema_period)
    atr = compute_atr(high, low, close, atr_period)
    upper = middle + (multiplier * atr)
    lower = middle - (multiplier * atr)

    return pd.DataFrame({
        "keltner_upper": upper,
        "keltner_middle": middle,
        "keltner_lower": lower
    }, index=close.index)


def compute_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3
) -> pd.DataFrame:
    """Calculates Stochastic Oscillator (%K and %D)."""
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)

    fast_k = 100.0 * (close - lowest_low) / denom
    slow_k = fast_k.rolling(window=3, min_periods=1).mean()
    slow_d = slow_k.rolling(window=d_period, min_periods=1).mean()

    return pd.DataFrame({
        "stoch_k": slow_k.bfill().fillna(50.0),
        "stoch_d": slow_d.bfill().fillna(50.0)
    }, index=close.index)


def compute_rolling_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 24
) -> pd.DataFrame:
    """Calculates Rolling Volume-Weighted Average Price (VWAP) and standard deviation bands."""
    typical_price = (high + low + close) / 3.0
    vol = volume.replace(0, 1e-6)
    pv = typical_price * vol

    rolling_pv = pv.rolling(window=period, min_periods=1).sum()
    rolling_vol = vol.rolling(window=period, min_periods=1).sum()

    vwap = rolling_pv / rolling_vol.replace(0, np.nan)
    std = typical_price.rolling(window=period, min_periods=1).std().fillna(0.0)

    upper = vwap + (2.0 * std)
    lower = vwap - (2.0 * std)

    return pd.DataFrame({
        "vwap": vwap.bfill(),
        "vwap_upper": upper.bfill(),
        "vwap_lower": lower.bfill()
    }, index=close.index)

