"""Unit tests for the Trading Strategy Lab dashboard server."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from src.dashboard.server import app

client = TestClient(app)


def test_dashboard_index_endpoint():
    """Verifies that the index page is served."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Strategy Lab" in response.text or "Laboratorio" in response.text


def test_api_strategies_endpoint():
    """Verifies that all 11 strategies are returned via API."""
    response = client.get("/api/strategies")
    assert response.status_code == 200
    data = response.json()
    assert "strategies" in data
    assert len(data["strategies"]) == 11
    ids = [s["id"] for s in data["strategies"]]
    assert "supertrend" in ids
    assert "donchian_breakout" in ids
    assert "trend_pullback_atr" in ids


def test_api_profiles_endpoint():
    """Verifies that risk profiles are returned."""
    response = client.get("/api/profiles")
    assert response.status_code == 200
    data = response.json()
    assert "profiles" in data
    assert "moderate" in data["profiles"]
    assert "conservative" in data["profiles"]
    assert "aggressive" in data["profiles"]


def test_api_backtest_endpoint():
    """Verifies executing backtest via API."""
    # Synthetic dataframe for download_ohlcv mock
    dates = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    prices = 40000.0 + np.cumsum(np.random.normal(0, 100, 100))
    mock_df = pd.DataFrame({
        "open": prices,
        "high": prices + 50.0,
        "low": prices - 50.0,
        "close": prices + 10.0,
        "volume": 1000.0
    }, index=dates)

    with patch("src.dashboard.server.BinanceDownloader.download_ohlcv", return_value=(mock_df, {})):
        response = client.post("/api/backtest", json={
            "strategy": "supertrend",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "profile": "moderate",
            "initial_capital": 10000.0
        })
        assert response.status_code == 200
        data = response.json()
        assert data["strategy_id"] == "supertrend"
        assert "metrics" in data
        assert "equity_curve" in data
        assert "trades" in data
        assert "verdict" in data
