"""Unit tests for Data Module (Downloader, CacheManager, DataValidator)."""
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data.cache_manager import CacheManager
from src.data.data_validator import DataValidationError, DataValidator
from src.data.downloader import BinanceDownloader


@pytest.fixture
def sample_ohlcv_df():
    """Generates a synthetic valid OHLCV DataFrame."""
    dates = pd.date_range(start="2023-01-01 00:00:00", periods=50, freq="1h", tz="UTC")
    np.random.seed(42)
    close = 20000 + np.cumsum(np.random.randn(50) * 50)
    open_p = close + np.random.randn(50) * 10
    high = np.maximum(open_p, close) + np.abs(np.random.randn(50) * 15)
    low = np.minimum(open_p, close) - np.abs(np.random.randn(50) * 15)
    volume = np.abs(np.random.randn(50) * 100) + 10

    df = pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    df.index.name = "datetime"
    return df


def test_validator_valid_data(sample_ohlcv_df):
    """Verifies that clean data passes validation with 0 gaps detected."""
    clean_df, meta = DataValidator.validate(sample_ohlcv_df, timeframe="1h")
    assert len(clean_df) == 50
    assert meta["gaps_detected"] == 0
    assert "close" in clean_df.columns


def test_validator_rejects_empty():
    """Verifies that empty dataframe raises DataValidationError."""
    with pytest.raises(DataValidationError):
        DataValidator.validate(pd.DataFrame(), timeframe="1h")


def test_validator_rejects_negative_price(sample_ohlcv_df):
    """Verifies that negative prices raise DataValidationError."""
    corrupted = sample_ohlcv_df.copy()
    corrupted.iloc[5, corrupted.columns.get_loc("close")] = -100.0
    with pytest.raises(DataValidationError):
        DataValidator.validate(corrupted, timeframe="1h")


def test_validator_detects_and_fills_gaps(sample_ohlcv_df):
    """Verifies that missing candles are detected and filled."""
    # Drop rows 10, 11, 12 to create a gap of 3 hours
    dropped_df = sample_ohlcv_df.drop(sample_ohlcv_df.index[10:13])
    assert len(dropped_df) == 47

    clean_df, meta = DataValidator.validate(dropped_df, timeframe="1h", fill_gaps=True)
    assert meta["gaps_detected"] == 3
    assert len(clean_df) == 50
    assert not clean_df.isnull().any().any()


def test_cache_manager_save_and_load(sample_ohlcv_df, tmp_path):
    """Tests saving to cache and reloading correctly."""
    cache = CacheManager(cache_dir=str(tmp_path))
    symbol = "BTC/USDT"
    tf = "1h"

    cache.save_data(sample_ohlcv_df, symbol, tf, market_type="futures")
    loaded_df, meta = cache.load_data(symbol, tf, market_type="futures")

    assert loaded_df is not None
    assert len(loaded_df) == len(sample_ohlcv_df)
    assert meta["symbol"] == symbol
    assert meta["candles_count"] == 50


def test_cache_manager_miss_on_future_dates(sample_ohlcv_df, tmp_path):
    """Tests cache miss when requesting a wider date range than available in cache."""
    cache = CacheManager(cache_dir=str(tmp_path))
    cache.save_data(sample_ohlcv_df, "BTC/USDT", "1h", market_type="futures")

    # Request start date earlier than cached data
    loaded_df, _ = cache.load_data("BTC/USDT", "1h", start_date="2022-01-01")
    assert loaded_df is None


def test_downloader_initialization():
    """Tests BinanceDownloader initialization."""
    downloader = BinanceDownloader()
    assert downloader.spot_exchange is not None
    assert downloader.futures_exchange is not None
