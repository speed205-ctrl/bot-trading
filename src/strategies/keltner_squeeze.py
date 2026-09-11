"""Strategy 8: Keltner Squeeze Breakout (TTM Squeeze adaptation)."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import (
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_keltner_channels,
    compute_macd,
)


class KeltnerSqueezeStrategy(BaseStrategy):
    """Volatility expansion strategy capturing explosive moves following a Bollinger/Keltner squeeze."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "kc_ema_period": 20,
            "kc_multiplier": 1.5,
            "ema_trend_period": 200,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.5,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "bb_std": [1.8, 2.0, 2.2],
            "kc_multiplier": [1.3, 1.5, 1.8],
            "atr_sl_mult": [1.5, 2.0, 2.5],
            "atr_tp_mult": [2.5, 3.5, 4.5],
        }

        super().__init__(
            name="Keltner Squeeze Breakout",
            description="Ruptura de volatilidad (TTM Squeeze) tras compresión de Bollinger dentro de Keltner con momentum positivo.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["bollinger_bands", "keltner_channels", "macd", "ema_200", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        bb_p = self.parameters.get("bb_period", 20)
        bb_std = self.parameters.get("bb_std", 2.0)
        kc_ema = self.parameters.get("kc_ema_period", 20)
        kc_mult = self.parameters.get("kc_multiplier", 1.5)
        trend_p = self.parameters.get("ema_trend_period", 200)
        atr_p = self.parameters.get("atr_period", 14)

        bb_df = compute_bollinger_bands(data["close"], period=bb_p, std_dev=bb_std)
        data["bb_upper"] = bb_df["bb_upper"]
        data["bb_lower"] = bb_df["bb_lower"]

        kc_df = compute_keltner_channels(data["high"], data["low"], data["close"], ema_period=kc_ema, multiplier=kc_mult)
        data["kc_upper"] = kc_df["keltner_upper"]
        data["kc_middle"] = kc_df["keltner_middle"]
        data["kc_lower"] = kc_df["keltner_lower"]

        # Squeeze definition: Bollinger completely inside Keltner
        data["is_squeezed"] = (data["bb_lower"] > data["kc_lower"]) & (data["bb_upper"] < data["kc_upper"])

        macd_df = compute_macd(data["close"], 12, 26, 9)
        data["macd_hist"] = macd_df["macd_hist"]

        data["ema_trend"] = compute_ema(data["close"], period=trend_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)
        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Squeeze fired: was squeezed on previous candle, but now Bollinger breaks outside Keltner
        2. MACD histogram > 0 (momentum is positive)
        3. Close > EMA 200
        """
        was_squeezed = df["is_squeezed"].shift(1) == True
        fired_up = df["bb_upper"] >= df["kc_upper"]
        squeeze_fired = was_squeezed & fired_up

        positive_momentum = df["macd_hist"] > 0
        trend_ok = df["close"] > df["ema_trend"]

        return (squeeze_fired & positive_momentum & trend_ok).astype(int)

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Close falls below Keltner midline or MACD histogram turns negative.
        """
        cross_below_kc = (df["close"].shift(1) >= df["kc_middle"].shift(1)) & (df["close"] < df["kc_middle"])
        return cross_below_kc.astype(int)
