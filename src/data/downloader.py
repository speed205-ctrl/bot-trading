"""Market data downloader from Binance public API using CCXT."""
import time
from typing import Any, Dict, Optional, Tuple
import ccxt
import pandas as pd

from src.data.cache_manager import CacheManager
from src.data.data_validator import DataValidator
from src.utils.logger import setup_logger

logger = setup_logger("Downloader")

TIMEFRAME_TO_MS = {
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


class BinanceDownloader:
    """Downloads historical OHLCV data from Binance without requiring API keys."""

    def __init__(self, cache_dir: str = "data/raw"):
        self.cache_manager = CacheManager(cache_dir)
        self.spot_exchange = ccxt.binance({
            "enableRateLimit": True,
            "timeout": 30000,
        })
        self.futures_exchange = ccxt.binance({
            "enableRateLimit": True,
            "timeout": 30000,
            "options": {"defaultType": "future"}
        })

    def _get_exchange(self, market_type: str):
        if market_type.lower() == "futures":
            return self.futures_exchange
        return self.spot_exchange

    def download_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        start_date: str = "2021-01-01",
        end_date: str = "2023-12-31",
        market_type: str = "futures",
        use_cache: bool = True,
        max_retries: int = 3
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Downloads historical OHLCV data with pagination, caching, and validation.

        Returns (DataFrame, metadata_dict).
        """
        if use_cache:
            cached_df, cached_meta = self.cache_manager.load_data(
                symbol=symbol,
                timeframe=timeframe,
                market_type=market_type,
                start_date=start_date,
                end_date=end_date
            )
            if cached_df is not None and not cached_df.empty:
                logger.info(f"Using cached data for {symbol} ({timeframe}, {market_type}) with {len(cached_df)} candles.")
                return cached_df, cached_meta or {}

        exchange = self._get_exchange(market_type)
        exchange.load_markets()

        # Format symbol if necessary for futures vs spot
        if market_type.lower() == "futures" and ":" not in symbol and symbol in exchange.markets:
            market_symbol = symbol
        elif symbol in exchange.markets:
            market_symbol = symbol
        else:
            # Fallback format for Binance futures in ccxt (e.g., BTC/USDT:USDT)
            futures_symbol = f"{symbol}:USDT"
            market_symbol = futures_symbol if futures_symbol in exchange.markets else symbol

        start_ts = int(pd.to_datetime(start_date, utc=True).timestamp() * 1000)
        end_ts = int(pd.to_datetime(end_date, utc=True).timestamp() * 1000)
        step_ms = TIMEFRAME_TO_MS.get(timeframe.lower(), 60 * 60 * 1000)
        limit = 1000  # Binance maximum candles per request

        logger.info(f"Downloading {symbol} [{timeframe}] from {start_date} to {end_date} ({market_type})...")

        all_ohlcv = []
        current_since = start_ts

        while current_since < end_ts:
            batch = None
            for attempt in range(1, max_retries + 1):
                try:
                    batch = exchange.fetch_ohlcv(
                        symbol=market_symbol,
                        timeframe=timeframe,
                        since=current_since,
                        limit=limit
                    )
                    break
                except Exception as e:
                    logger.warning(f"Fetch attempt {attempt}/{max_retries} failed for {market_symbol} at {current_since}: {e}")
                    if attempt == max_retries:
                        raise ConnectionError(f"Failed to fetch data from Binance after {max_retries} attempts: {e}")
                    time.sleep(1.5 * attempt)

            if not batch:
                logger.warning(f"No candles returned for {market_symbol} at {current_since}. Finishing download loop.")
                break

            all_ohlcv.extend(batch)
            last_ts = batch[-1][0]

            # If last candle reaches or passes end_ts, stop
            if last_ts >= end_ts or len(batch) < 2:
                break

            # Avoid infinite loop if exchange returns same timestamp
            if last_ts <= current_since:
                current_since += step_ms * len(batch)
            else:
                current_since = last_ts + step_ms

            time.sleep(exchange.rateLimit / 1000.0)

        if not all_ohlcv:
            raise ValueError(f"No OHLCV data was downloaded for {symbol} ({start_date} to {end_date}).")

        # Construct DataFrame
        df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("datetime", inplace=True)
        df.drop(columns=["timestamp"], inplace=True)

        # Filter precisely to end_date
        df = df[df.index <= pd.to_datetime(end_date, utc=True)]

        # Validate and clean data
        validated_df, meta = DataValidator.validate(df, timeframe=timeframe, fill_gaps=True)

        # Save to cache
        self.cache_manager.save_data(
            df=validated_df,
            symbol=symbol,
            timeframe=timeframe,
            market_type=market_type,
            metadata=meta
        )

        return validated_df, meta
