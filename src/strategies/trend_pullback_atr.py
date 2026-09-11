"""Strategy 1: Trend Pullback ATR."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_ema, compute_rsi


class TrendPullbackATRStrategy(BaseStrategy):
    """Trend following strategy with RSI pullback entry above EMA 200 and ATR-based stops/targets."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "ema_period": 200,
            "rsi_period": 14,
            "atr_period": 14,
            "rsi_oversold": 30,
            "rsi_exit": 70,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.0,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "rsi_oversold": [25, 30, 35, 40],
            "atr_sl_mult": [1.5, 2.0, 2.5, 3.0],
            "atr_tp_mult": [2.0, 3.0, 4.0, 5.0],
            "rsi_exit": [65, 70, 75, 80],
        }

        super().__init__(
            name="Trend Pullback ATR",
            description="Seguimiento de tendencia con entrada en retroceso RSI sobre EMA 200 y salidas por ATR y RSI sobrecompra.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["ema_200", "rsi_14", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates EMA 200, RSI, and ATR."""
        data = df.copy()
        ema_p = self.parameters.get("ema_period", 200)
        rsi_p = self.parameters.get("rsi_period", 14)
        atr_p = self.parameters.get("atr_period", 14)

        data["ema_trend"] = compute_ema(data["close"], ema_p)
        data["rsi"] = compute_rsi(data["close"], rsi_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], atr_p)

        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Close > EMA 200
        2. Previous candle RSI < rsi_oversold
        3. Current candle RSI >= rsi_oversold (crossing back up)
        """
        oversold = self.parameters.get("rsi_oversold", 30)

        trend_condition = df["close"] > df["ema_trend"]
        prev_rsi_oversold = df["rsi"].shift(1) < oversold
        curr_rsi_recovered = df["rsi"] >= oversold
        rsi_cross_up = prev_rsi_oversold & curr_rsi_recovered

        entry_signal = (trend_condition & rsi_cross_up).astype(int)
        return entry_signal

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Alternative signal when RSI >= rsi_exit (overbought).
        """
        rsi_exit_threshold = self.parameters.get("rsi_exit", 70)
        exit_signal = (df["rsi"] >= rsi_exit_threshold).astype(int)
        return exit_signal
