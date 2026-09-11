"""Strategy 10: Reversión a la Media con VWAP Rodante."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_ema, compute_rolling_vwap


class VwapMeanReversionStrategy(BaseStrategy):
    """Institutional mean reversion strategy capitalizing on price deviations from the Rolling VWAP."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "vwap_period": 24,  # 24 hours rolling
            "ema_trend_period": 200,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.0,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "vwap_period": [18, 24, 30],
            "atr_sl_mult": [1.5, 2.0, 2.5],
            "atr_tp_mult": [2.0, 3.0, 4.0],
        }

        super().__init__(
            name="Reversión a la Media con VWAP Rodante",
            description="Reversión a la media institucional operando desviaciones estándar bajo el VWAP rodante en macro-tendencia.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["rolling_vwap", "ema_200", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        vwap_p = self.parameters.get("vwap_period", 24)
        trend_p = self.parameters.get("ema_trend_period", 200)
        atr_p = self.parameters.get("atr_period", 14)

        vwap_df = compute_rolling_vwap(data["high"], data["low"], data["close"], data["volume"], period=vwap_p)
        data["vwap"] = vwap_df["vwap"]
        data["vwap_upper"] = vwap_df["vwap_upper"]
        data["vwap_lower"] = vwap_df["vwap_lower"]

        data["ema_trend"] = compute_ema(data["close"], period=trend_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)
        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Close > EMA 200
        2. Low touched or pierced vwap_lower, but Close rebounded back above vwap_lower
        """
        trend_ok = df["close"] > df["ema_trend"]
        pierced_lower = df["low"] <= df["vwap_lower"]
        closed_above_lower = df["close"] > df["vwap_lower"]

        return (trend_ok & pierced_lower & closed_above_lower).astype(int)

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Price reaches or crosses above the VWAP midline.
        """
        reached_vwap = (df["close"].shift(1) < df["vwap"].shift(1)) & (df["close"] >= df["vwap"])
        return reached_vwap.astype(int)
