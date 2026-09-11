"""Strategy 4: Reversión a la Media con RSI."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_ema, compute_rsi


class RsiMeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy capturing oversold dips aligned with macro trend (EMA 200)."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_exit": 50,
            "ema_trend_period": 200,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.0,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "rsi_period": [7, 10, 14, 21],
            "rsi_oversold": [20, 25, 30, 35],
            "rsi_exit": [45, 50, 55, 60],
            "atr_sl_mult": [1.5, 2.0, 2.5, 3.0],
            "atr_tp_mult": [2.0, 3.0, 4.0, 5.0],
        }

        super().__init__(
            name="Reversión a la Media con RSI",
            description="Entrada en retroceso sobrevendido a favor de la macro-tendencia con salida al nivel neutral.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["rsi", "ema_200", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        rsi_p = self.parameters.get("rsi_period", 14)
        trend_p = self.parameters.get("ema_trend_period", 200)
        atr_p = self.parameters.get("atr_period", 14)

        data["rsi"] = compute_rsi(data["close"], period=rsi_p)
        data["ema_trend"] = compute_ema(data["close"], period=trend_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)

        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Close > EMA 200
        2. RSI fell below oversold level on previous candle
        3. RSI crosses back above oversold level on current candle
        """
        oversold = self.parameters.get("rsi_oversold", 30)

        trend_condition = df["close"] > df["ema_trend"]
        was_oversold = df["rsi"].shift(1) < oversold
        crossed_up = df["rsi"] >= oversold

        entry_signal = (trend_condition & was_oversold & crossed_up).astype(int)
        return entry_signal

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        RSI reaches or crosses above exit level (equilibrium/mean).
        """
        exit_th = self.parameters.get("rsi_exit", 50)
        return (df["rsi"] >= exit_th).astype(int)
