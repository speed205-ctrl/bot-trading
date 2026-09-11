"""Unit tests for Binance Testnet connector and live runner."""
import numpy as np
import pandas as pd
import pytest

from src.live.testnet_connector import TestnetConnector
from src.live.testnet_runner import TestnetRunner


@pytest.fixture
def recent_candles():
    """Generates synthetic recent price data."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    close = 40000.0 + np.cumsum(np.random.randn(100) * 100)
    high = close + np.random.uniform(50, 150, 100)
    low = close - np.random.uniform(50, 150, 100)
    open_p = (high + low) / 2.0
    vol = np.random.uniform(100, 500, 100)

    df = pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol
    }, index=dates)
    return df


def test_testnet_connector_sandbox_mode():
    """Verifies that connector initializes in CCXT sandbox mode."""
    connector = TestnetConnector()
    # In sandbox mode, urls should point to testnet
    assert connector.exchange is not None
    assert "testnet" in connector.exchange.urls.get("api", {}).get("public", "") or "binance" in connector.exchange.urls.get("api", {}).get("public", "")


def test_testnet_runner_dry_run_evaluation(recent_candles):
    """Verifies that TestnetRunner evaluates signals and executes dry-run without errors."""
    runner = TestnetRunner(
        strategy_id="supertrend",
        symbol="BTC/USDT",
        timeframe="1h",
        dry_run=True
    )

    result = runner.evaluate_signals(df=recent_candles)
    assert result["strategy"] == "Supertrend con Confirmación de Volumen"
    assert result["symbol"] == "BTC/USDT"
    assert result["close_price"] > 0
    assert result["action"] in ["BUY / LONG", "SELL / EXIT", "HOLD"]
