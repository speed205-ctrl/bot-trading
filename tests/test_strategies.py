"""Unit tests for technical indicators and strategy framework."""
import numpy as np
import pandas as pd
import pytest

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import (
    compute_adx,
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
)
from src.strategies.trend_pullback_atr import TrendPullbackATRStrategy


@pytest.fixture
def ohlcv_series():
    """Generates synthetic price data for indicator verification."""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    close = 100.0 + np.cumsum(np.random.randn(n) * 2)
    high = close + np.random.uniform(0.5, 3.0, n)
    low = close - np.random.uniform(0.5, 3.0, n)
    open_p = (high + low) / 2.0
    volume = np.random.uniform(100, 1000, n)

    df = pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    return df


def test_indicators_math(ohlcv_series):
    """Verifies bounds and consistency of technical indicators."""
    close = ohlcv_series["close"]
    high = ohlcv_series["high"]
    low = ohlcv_series["low"]

    # EMA & SMA
    ema = compute_ema(close, 20)
    sma = compute_sma(close, 20)
    assert len(ema) == len(close)
    assert not ema.isnull().any()

    # RSI (0 <= RSI <= 100)
    rsi = compute_rsi(close, 14)
    assert rsi.min() >= 0.0
    assert rsi.max() <= 100.0

    # ATR (always positive)
    atr = compute_atr(high, low, close, 14)
    assert (atr > 0).all()

    # Bollinger Bands (upper >= middle >= lower)
    bb = compute_bollinger_bands(close, period=20, std_dev=2.0)
    valid_idx = bb.dropna().index
    assert (bb.loc[valid_idx, "bb_upper"] >= bb.loc[valid_idx, "bb_middle"]).all()
    assert (bb.loc[valid_idx, "bb_middle"] >= bb.loc[valid_idx, "bb_lower"]).all()

    # ADX (>= 0)
    adx_df = compute_adx(high, low, close, period=14)
    assert (adx_df["adx"] >= 0).all()

    # MACD
    macd = compute_macd(close, 12, 26, 9)
    assert "macd_line" in macd.columns
    assert "macd_signal" in macd.columns
    assert "macd_hist" in macd.columns


def test_base_strategy_immutability(ohlcv_series):
    """Verifies that strategy execution never mutates input DataFrame."""
    strategy = TrendPullbackATRStrategy()
    original_cols = list(ohlcv_series.columns)
    original_len = len(ohlcv_series)

    prepared = strategy.prepare_data(ohlcv_series)

    # Original dataframe should remain completely unchanged
    assert list(ohlcv_series.columns) == original_cols
    assert len(ohlcv_series) == original_len
    # Prepared dataframe has indicators and signals
    assert "entry_signal" in prepared.columns
    assert "exit_signal" in prepared.columns
    assert set(prepared["entry_signal"].unique()).issubset({0, 1})
    assert set(prepared["exit_signal"].unique()).issubset({0, 1})


def test_trend_pullback_atr_stops(ohlcv_series):
    """Verifies stop-loss and take-profit calculation."""
    strategy = TrendPullbackATRStrategy(parameters={"atr_sl_mult": 2.0, "atr_tp_mult": 3.0})
    entry = 50000.0
    atr = 500.0
    row = pd.Series()

    sl = strategy.get_stop_loss(entry, atr, row)
    tp = strategy.get_take_profit(entry, atr, row)

    assert sl == 50000.0 - (2.0 * 500.0)  # 49,000
    assert tp == 50000.0 + (3.0 * 500.0)  # 51,500
