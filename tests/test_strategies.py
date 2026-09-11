"""Unit tests for all 11 trading strategies and technical indicators."""
import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine
from src.strategies import STRATEGY_REGISTRY, get_strategy
from src.strategies.indicators import (
    compute_adx,
    compute_atr,
    compute_bollinger_bands,
    compute_donchian_channels,
    compute_ema,
    compute_keltner_channels,
    compute_macd,
    compute_rolling_vwap,
    compute_rsi,
    compute_sma,
    compute_stochastic,
    compute_supertrend,
)


@pytest.fixture
def ohlcv_series():
    """Generates synthetic price data for indicator and strategy verification."""
    np.random.seed(42)
    n = 250  # Covers 200 EMA
    dates = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    trend = np.linspace(100.0, 150.0, n)
    noise = np.sin(np.linspace(0, 12 * np.pi, n)) * 10
    close = trend + noise
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
    """Verifies bounds and consistency of all technical indicators."""
    close = ohlcv_series["close"]
    high = ohlcv_series["high"]
    low = ohlcv_series["low"]
    vol = ohlcv_series["volume"]

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

    # Bollinger Bands
    bb = compute_bollinger_bands(close, period=20, std_dev=2.0)
    valid_idx = bb.dropna().index
    assert (bb.loc[valid_idx, "bb_upper"] >= bb.loc[valid_idx, "bb_middle"]).all()
    assert (bb.loc[valid_idx, "bb_middle"] >= bb.loc[valid_idx, "bb_lower"]).all()

    # ADX
    adx_df = compute_adx(high, low, close, period=14)
    assert (adx_df["adx"] >= 0).all()

    # MACD
    macd = compute_macd(close, 12, 26, 9)
    assert "macd_line" in macd.columns

    # Supertrend
    st = compute_supertrend(high, low, close, period=10, multiplier=3.0)
    assert "supertrend" in st.columns
    assert set(st["supertrend_direction"].unique()).issubset({-1, 1})

    # Donchian Channels
    dc = compute_donchian_channels(high, low, period=20)
    assert (dc["donchian_upper"] >= dc["donchian_lower"]).all()

    # Keltner Channels
    kc = compute_keltner_channels(high, low, close, ema_period=20, multiplier=1.5)
    assert (kc["keltner_upper"] >= kc["keltner_lower"]).all()

    # Stochastic
    stoch = compute_stochastic(high, low, close, k_period=14, d_period=3)
    assert stoch["stoch_k"].min() >= 0.0
    assert stoch["stoch_k"].max() <= 100.0

    # Rolling VWAP
    vwap = compute_rolling_vwap(high, low, close, vol, period=24)
    assert (vwap["vwap_upper"] >= vwap["vwap_lower"]).all()


@pytest.mark.parametrize("strategy_id", list(STRATEGY_REGISTRY.keys()))
def test_all_11_strategies_prepare_and_run(strategy_id, ohlcv_series):
    """Tests that all 11 strategies instantiate, prepare data with binary signals, and run through the backtest engine."""
    strategy = get_strategy(strategy_id)
    assert strategy.preferred_timeframe == "1h"
    assert strategy.direction == "long_only"
    assert len(strategy.parameters) > 0

    # Prepare data
    prepared = strategy.prepare_data(ohlcv_series)
    assert "entry_signal" in prepared.columns
    assert "exit_signal" in prepared.columns
    assert "atr" in prepared.columns
    assert set(prepared["entry_signal"].unique()).issubset({0, 1})
    assert set(prepared["exit_signal"].unique()).issubset({0, 1})

    # Execute in Backtest Engine
    engine = BacktestEngine(initial_capital=10000.0, risk_profile="moderate")
    res = engine.run(strategy, ohlcv_series, symbol="BTC/USDT")
    assert res.strategy_name == strategy.name
    assert not res.equity_curve.empty
    assert res.final_equity > 0
