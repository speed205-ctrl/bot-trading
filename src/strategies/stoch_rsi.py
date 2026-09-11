"""Strategy 9: Doble Momentum Estocástico + RSI."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_ema, compute_rsi, compute_stochastic


class StochRsiMeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy requiring synchronous oversold conditions across RSI and Stochastic in macro uptrend."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "rsi_period": 14,
            "rsi_oversold": 35,
            "stoch_k_period": 14,
            "stoch_d_period": 3,
            "stoch_oversold": 25,
            "stoch_exit": 75,
            "ema_trend_period": 200,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.0,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "rsi_oversold": [30, 35, 40],
            "stoch_oversold": [20, 25, 30],
            "atr_sl_mult": [1.5, 2.0, 2.5],
            "atr_tp_mult": [2.5, 3.0, 4.0],
        }

        super().__init__(
            name="Doble Momentum Estocástico + RSI",
            description="Reversión a la media con sobreventa sincrónica en RSI y Estocástico a favor de la macro-tendencia (EMA 200).",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["rsi", "stochastic", "ema_200", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        rsi_p = self.parameters.get("rsi_period", 14)
        k_p = self.parameters.get("stoch_k_period", 14)
        d_p = self.parameters.get("stoch_d_period", 3)
        trend_p = self.parameters.get("ema_trend_period", 200)
        atr_p = self.parameters.get("atr_period", 14)

        data["rsi"] = compute_rsi(data["close"], period=rsi_p)
        stoch_df = compute_stochastic(data["high"], data["low"], data["close"], k_period=k_p, d_period=d_p)
        data["stoch_k"] = stoch_df["stoch_k"]
        data["stoch_d"] = stoch_df["stoch_d"]

        data["ema_trend"] = compute_ema(data["close"], period=trend_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)
        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Close > EMA 200
        2. RSI < rsi_oversold
        3. Stoch %K crosses above %D while below stoch_oversold
        """
        rsi_os = self.parameters.get("rsi_oversold", 35)
        stoch_os = self.parameters.get("stoch_oversold", 25)

        trend_ok = df["close"] > df["ema_trend"]
        rsi_ok = df["rsi"] < rsi_os

        stoch_below = df["stoch_k"].shift(1) < stoch_os
        stoch_cross = (df["stoch_k"].shift(1) <= df["stoch_d"].shift(1)) & (df["stoch_k"] > df["stoch_d"])
        stoch_signal = stoch_below & stoch_cross

        return (trend_ok & rsi_ok & stoch_signal).astype(int)

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Stochastic %K exceeds stoch_exit level.
        """
        stoch_exit_level = self.parameters.get("stoch_exit", 75)
        return (df["stoch_k"] >= stoch_exit_level).astype(int)
