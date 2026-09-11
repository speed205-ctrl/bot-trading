"""Cache manager for local storage of historical market data."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pandas as pd

from src.utils.logger import setup_logger

logger = setup_logger("CacheManager")


class CacheManager:
    """Handles saving and loading market data from local disk cache."""

    def __init__(self, cache_dir: str = "data/raw"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, symbol: str, timeframe: str, market_type: str) -> Path:
        """Constructs standardized filename for market data cache."""
        clean_symbol = symbol.replace("/", "_").replace(":", "_").upper()
        filename = f"{clean_symbol}_{timeframe}_{market_type.lower()}.csv"
        return self.cache_dir / filename

    def _get_meta_path(self, file_path: Path) -> Path:
        """Returns the corresponding metadata JSON path."""
        return file_path.with_suffix(".json")

    def save_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        market_type: str = "futures",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Saves market data DataFrame and its metadata to cache."""
        file_path = self._get_file_path(symbol, timeframe, market_type)
        meta_path = self._get_meta_path(file_path)

        # Ensure datetime index is preserved or saved as ISO string column
        save_df = df.copy()
        if "datetime" not in save_df.columns:
            if isinstance(save_df.index, pd.DatetimeIndex):
                save_df = save_df.reset_index()
                save_df.rename(columns={"index": "datetime"}, inplace=True)

        save_df.to_csv(file_path, index=False)

        meta = metadata or {}
        meta.update({
            "symbol": symbol,
            "timeframe": timeframe,
            "market_type": market_type,
            "candles_count": len(save_df),
            "start_time": str(save_df["datetime"].min()) if not save_df.empty and "datetime" in save_df.columns else None,
            "end_time": str(save_df["datetime"].max()) if not save_df.empty and "datetime" in save_df.columns else None,
        })

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Saved {len(save_df)} candles to cache: {file_path}")
        return file_path

    def load_data(
        self,
        symbol: str,
        timeframe: str,
        market_type: str = "futures",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
        """Loads market data from cache if it exists and covers the requested range."""
        file_path = self._get_file_path(symbol, timeframe, market_type)
        meta_path = self._get_meta_path(file_path)

        if not file_path.exists():
            return None, None

        try:
            df = pd.read_csv(file_path)
            if "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
                df.set_index("datetime", inplace=True)
            elif "timestamp" in df.columns:
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                df.set_index("datetime", inplace=True)

            metadata = {}
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

            # Check date range coverage if specified
            if start_date and not df.empty:
                req_start = pd.to_datetime(start_date, utc=True)
                if df.index.min() > req_start:
                    logger.debug(f"Cache miss: start date {df.index.min()} is after requested {req_start}")
                    return None, None

            if end_date and not df.empty:
                req_end = pd.to_datetime(end_date, utc=True)
                if df.index.max() < req_end:
                    logger.debug(f"Cache miss: end date {df.index.max()} is before requested {req_end}")
                    return None, None

            # Filter to requested range
            if start_date:
                df = df[df.index >= pd.to_datetime(start_date, utc=True)]
            if end_date:
                df = df[df.index <= pd.to_datetime(end_date, utc=True)]

            logger.info(f"Loaded {len(df)} candles from cache: {file_path}")
            return df, metadata

        except Exception as e:
            logger.warning(f"Failed to read cache {file_path}: {e}")
            return None, None
