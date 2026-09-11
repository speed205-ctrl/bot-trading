"""Strategy 7: Breakout de Canales de Donchian (Turtle Trading)."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_donchian_channels, compute_ema


class DonchianBreakoutStrategy(BaseStrategy):
    """Trend breakout strategy based on Donchian Channels with EMA 200 filter."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "entry_period": 20,
            "exit_period": 10,
            "ema_trend_period": 200,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 4.0,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "entry_period": [15, 20, 25, 30],
            "exit_period": [7, 10, 14],
            "atr_sl_mult": [1.5, 2.0, 2.5],
            "atr_tp_mult": [3.0, 4.0, 5.0],
        }

        super().__init__(
            name="Breakout de Canales de Donchian",
            description="Ruptura de máximos de 20 periodos (Turtle Trading) con salida en mínimos de 10 periodos y filtro EMA 200.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["donchian_channels", "ema_200", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        entry_p = self.parameters.get("entry_period", 20)
        exit_p = self.parameters.get("exit_period", 10)
        trend_p = self.parameters.get("ema_trend_period", 200)
        atr_p = self.parameters.get("atr_period", 14)

        entry_dc = compute_donchian_channels(data["high"], data["low"], period=entry_p)
        data["dc_upper"] = entry_dc["donchian_upper"]
        data["dc_middle"] = entry_dc["donchian_middle"]

        exit_dc = compute_donchian_channels(data["high"], data["low"], period=exit_p)
        data["dc_exit_lower"] = exit_dc["donchian_lower"]

        data["ema_trend"] = compute_ema(data["close"], period=trend_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)
        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Close > Previous candle's 20-period highest high
        2. Close > EMA 200
        """
        breakout = df["close"] > df["dc_upper"].shift(1)
        trend_ok = df["close"] > df["ema_trend"]

        return (breakout & trend_ok).astype(int)

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Close falls below previous candle's 10-period lowest low.
        """
        exit_break = df["close"] < df["dc_exit_lower"].shift(1)
        return exit_break.astype(int)
