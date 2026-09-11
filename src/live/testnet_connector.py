"""Binance Testnet connector using CCXT Sandbox mode."""
import os
from pathlib import Path
from typing import Any, Dict, Optional
import ccxt
import pandas as pd
import yaml

from src.utils.logger import setup_logger

logger = setup_logger("TestnetConnector")


class TestnetConnector:
    """Handles API communication with Binance Testnet in sandbox mode."""
    __test__ = False

    def __init__(self, config_path: str = "config/testnet_config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

        market_type = self.config.get("testnet", {}).get("market_type", "futures")
        api_key = os.getenv("BINANCE_TESTNET_API_KEY") or self.config.get("credentials", {}).get("api_key", "")
        api_secret = os.getenv("BINANCE_TESTNET_SECRET") or self.config.get("credentials", {}).get("api_secret", "")

        options = {}
        if market_type == "futures":
            options["defaultType"] = "future"

        self.exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": options
        })

        # Activate CCXT Sandbox Mode for Binance Testnet
        self.exchange.set_sandbox_mode(True)
        self.has_credentials = bool(api_key and api_secret)

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def test_connection(self) -> Dict[str, Any]:
        """Tests connection to Binance Testnet sandbox."""
        logger.info(f"Connecting to Binance Testnet sandbox ({self.exchange.urls['api']})...")
        try:
            markets = self.exchange.load_markets()
            status = self.exchange.fetch_status() if hasattr(self.exchange, "fetch_status") else {"status": "ok"}
            balance = None

            if self.has_credentials:
                try:
                    balance = self.exchange.fetch_balance()
                except Exception as be:
                    logger.warning(f"Could not fetch testnet balance: {be}")

            return {
                "success": True,
                "sandbox_mode": True,
                "markets_loaded": len(markets),
                "status": status,
                "has_credentials": self.has_credentials,
                "balance": balance
            }
        except Exception as e:
            logger.error(f"Testnet connection failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "has_credentials": self.has_credentials
            }

    def fetch_recent_data(self, symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 250) -> pd.DataFrame:
        """Fetches the most recent completed candles for live signal evaluation."""
        if not self.exchange.markets:
            self.exchange.load_markets()

        formatted_symbol = symbol
        if self.exchange.options.get("defaultType") == "future" and ":" not in symbol:
            futures_symbol = f"{symbol}:USDT"
            if futures_symbol in self.exchange.markets:
                formatted_symbol = futures_symbol

        ohlcv = self.exchange.fetch_ohlcv(formatted_symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("datetime", inplace=True)
        df.drop(columns=["timestamp"], inplace=True)
        return df

    def place_testnet_order(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        amount: float,
        order_type: str = "market",
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Submits a real order to Binance Testnet."""
        if not self.has_credentials:
            raise ValueError("Testnet credentials (API Key and Secret) are required to place orders.")

        if not self.exchange.markets:
            self.exchange.load_markets()

        formatted_symbol = symbol
        if self.exchange.options.get("defaultType") == "future" and ":" not in symbol:
            futures_symbol = f"{symbol}:USDT"
            if futures_symbol in self.exchange.markets:
                formatted_symbol = futures_symbol

        logger.info(f"Submitting Testnet order: {side.upper()} {amount} of {formatted_symbol} ({order_type})...")
        order = self.exchange.create_order(
            symbol=formatted_symbol,
            type=order_type,
            side=side.lower(),
            amount=amount,
            price=price
        )
        logger.info(f"Testnet order filled! Order ID: {order.get('id')}")
        return order
