"""Strategy 2: Cruce de EMAs con Filtro ADX."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_adx, compute_atr, compute_ema


class EmaCrossADXStrategy(BaseStrategy):
    """Momentum strategy combining fast/slow EMA crossover with ADX strength filter and EMA 200."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "ema_fast": 9,
            "ema_slow": 21,
            "ema_trend_period": 200,
            "adx_period": 14,
            "adx_threshold": 25,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.0,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "ema_fast": [7, 9, 12, 15],
            "ema_slow": [18, 21, 25, 30],
            "adx_threshold": [20, 25, 30, 35],
            "atr_sl_mult": [1.5, 2.0, 2.5, 3.0],
            "atr_tp_mult": [2.0, 3.0, 4.0, 5.0],
        }

        super().__init__(
            name="Cruce de EMAs con Filtro ADX",
            description="Momentum con filtro de fuerza de tendencia ADX y filtro macro EMA 200.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["ema_fast", "ema_slow", "ema_200", "adx_14", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        fast_p = self.parameters.get("ema_fast", 9)
        slow_p = self.parameters.get("ema_slow", 21)
        trend_p = self.parameters.get("ema_trend_period", 200)
        adx_p = self.parameters.get("adx_period", 14)
        atr_p = self.parameters.get("atr_period", 14)

        data["ema_fast"] = compute_ema(data["close"], fast_p)
        data["ema_slow"] = compute_ema(data["close"], slow_p)
        data["ema_trend"] = compute_ema(data["close"], trend_p)

        adx_res = compute_adx(data["high"], data["low"], data["close"], adx_p)
        data["adx"] = adx_res["adx"]
        data["plus_di"] = adx_res["plus_di"]
        data["minus_di"] = adx_res["minus_di"]

        data["atr"] = compute_atr(data["high"], data["low"], data["close"], atr_p)
        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Fast EMA crosses above Slow EMA
        2. ADX > adx_threshold
        3. Close > EMA 200
        """
        adx_thresh = self.parameters.get("adx_threshold", 25)

        prev_fast_below = df["ema_fast"].shift(1) <= df["ema_slow"].shift(1)
        curr_fast_above = df["ema_fast"] > df["ema_slow"]
        ema_cross_up = prev_fast_below & curr_fast_above

        adx_filter = df["adx"] > adx_thresh
        trend_filter = df["close"] > df["ema_trend"]

        entry_signal = (ema_cross_up & adx_filter & trend_filter).astype(int)
        return entry_signal

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Fast EMA crosses below Slow EMA
        """
        prev_fast_above = df["ema_fast"].shift(1) >= df["ema_slow"].shift(1)
        curr_fast_below = df["ema_fast"] < df["ema_slow"]
        ema_cross_down = prev_fast_above & curr_fast_below

        return ema_cross_down.astype(int)
