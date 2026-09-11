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
