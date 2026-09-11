"""Data validator for market OHLCV data."""
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from src.utils.logger import setup_logger

logger = setup_logger("DataValidator")

# Mapping timeframes to pandas frequency strings
TIMEFRAME_TO_FREQ = {
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


class DataValidationError(Exception):
    """Raised when data fails strict validation."""
    pass


class DataValidator:
    """Validates and sanitizes OHLCV DataFrame."""

    REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

    @classmethod
    def validate(
        cls,
        df: pd.DataFrame,
        timeframe: str = "1h",
        fill_gaps: bool = True
    ) -> Tuple[pd.DataFrame, Dict]:
        """Validates OHLCV DataFrame integrity and returns sanitized dataframe with metadata report."""
        if df.empty:
            raise DataValidationError("DataFrame is empty.")

        clean_df = df.copy()

        # Ensure datetime index
        if not isinstance(clean_df.index, pd.DatetimeIndex):
            if "datetime" in clean_df.columns:
                clean_df["datetime"] = pd.to_datetime(clean_df["datetime"], utc=True)
                clean_df.set_index("datetime", inplace=True)
            elif "timestamp" in clean_df.columns:
                clean_df["datetime"] = pd.to_datetime(clean_df["timestamp"], unit="ms", utc=True)
                clean_df.set_index("datetime", inplace=True)
            else:
                raise DataValidationError("DataFrame must have a DatetimeIndex, 'datetime' or 'timestamp' column.")

        # Ensure UTC timezone
        if clean_df.index.tz is None:
            clean_df.index = clean_df.index.tz_localize("UTC")
        else:
            clean_df.index = clean_df.index.tz_convert("UTC")

        # Standardize column names to lowercase
        clean_df.columns = [c.lower() for c in clean_df.columns]

        for col in cls.REQUIRED_COLUMNS:
            if col not in clean_df.columns:
                raise DataValidationError(f"Missing required OHLCV column: '{col}'.")

        # Sort chronologically and drop duplicate timestamps
        clean_df = clean_df.sort_index()
        duplicates_count = clean_df.index.duplicated().sum()
        if duplicates_count > 0:
            logger.warning(f"Found {duplicates_count} duplicate timestamps. Dropping duplicates.")
            clean_df = clean_df[~clean_df.index.duplicated(keep="first")]

        # Validate numeric types and no nulls
        for col in cls.REQUIRED_COLUMNS:
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")

        null_counts = clean_df[cls.REQUIRED_COLUMNS].isnull().sum()
        if null_counts.sum() > 0:
            raise DataValidationError(f"Found null values in data: {null_counts.to_dict()}")

        # Check for non-positive prices or negative volume
        if (clean_df[["open", "high", "low", "close"]] <= 0).any().any():
            raise DataValidationError("Found zero or negative prices in OHLC columns.")

        if (clean_df["volume"] < 0).any():
            raise DataValidationError("Found negative volume values.")

        # Price logic checks: High must be >= Low, High >= Open, High >= Close, etc.
        invalid_high_low = (clean_df["high"] < clean_df["low"]).sum()
        invalid_high_open = (clean_df["high"] < clean_df["open"]).sum()
        invalid_high_close = (clean_df["high"] < clean_df["close"]).sum()
        invalid_low_open = (clean_df["low"] > clean_df["open"]).sum()
        invalid_low_close = (clean_df["low"] > clean_df["close"]).sum()

        if (invalid_high_low + invalid_high_open + invalid_high_close + invalid_low_open + invalid_low_close) > 0:
            logger.warning("Discrepancies found in candle high/low bounds. Fixing bounds.")
            clean_df["high"] = clean_df[["open", "high", "low", "close"]].max(axis=1)
            clean_df["low"] = clean_df[["open", "high", "low", "close"]].min(axis=1)

        # Gap detection
        freq = TIMEFRAME_TO_FREQ.get(timeframe.lower(), "1h")
        expected_range = pd.date_range(start=clean_df.index.min(), end=clean_df.index.max(), freq=freq, tz="UTC")
        missing_timestamps = expected_range.difference(clean_df.index)
        gaps_detected = len(missing_timestamps)

        if gaps_detected > 0:
            logger.info(f"Detected {gaps_detected} missing candles for timeframe {timeframe}.")
            if fill_gaps:
                clean_df = clean_df.reindex(expected_range)
                # Forward fill close, then backfill remaining OHLC with close
                clean_df["close"] = clean_df["close"].ffill().bfill()
                clean_df["open"] = clean_df["open"].fillna(clean_df["close"])
                clean_df["high"] = clean_df["high"].fillna(clean_df["close"])
                clean_df["low"] = clean_df["low"].fillna(clean_df["close"])
                clean_df["volume"] = clean_df["volume"].fillna(0.0)
                clean_df.index.name = "datetime"
                logger.info(f"Successfully filled {gaps_detected} missing candles.")

        metadata = {
            "total_candles": len(clean_df),
            "start_time": str(clean_df.index.min()),
            "end_time": str(clean_df.index.max()),
            "gaps_detected": gaps_detected,
            "gaps_filled": gaps_detected if fill_gaps else 0,
            "duplicates_removed": int(duplicates_count)
        }

        return clean_df, metadata
