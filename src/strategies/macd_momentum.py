"""Strategy 5: Momentum MACD con Volumen."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_ema, compute_macd, compute_sma


class MacdMomentumStrategy(BaseStrategy):
    """Momentum strategy combining MACD crossover with volume surge and EMA 200 trend filter."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "vol_factor": 1.3,
            "ema_trend_period": 200,
            "vol_sma_period": 20,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.0,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "macd_fast": [8, 10, 12, 16],
            "macd_slow": [21, 24, 26, 31],
            "macd_signal": [7, 9, 11],
            "vol_factor": [1.0, 1.3, 1.6, 2.0],
            "atr_sl_mult": [1.5, 2.0, 2.5, 3.0],
            "atr_tp_mult": [2.0, 3.0, 4.0, 5.0],
        }

        super().__init__(
            name="Momentum MACD con Volumen",
            description="Cruce de MACD alcista con confirmación de volumen extraordinario y alineación con EMA 200.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["macd", "ema_200", "volume_sma", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        fast_p = self.parameters.get("macd_fast", 12)
        slow_p = self.parameters.get("macd_slow", 26)
        sig_p = self.parameters.get("macd_signal", 9)
        trend_p = self.parameters.get("ema_trend_period", 200)
        vol_p = self.parameters.get("vol_sma_period", 20)
        atr_p = self.parameters.get("atr_period", 14)

        macd_df = compute_macd(data["close"], fast_period=fast_p, slow_period=slow_p, signal_period=sig_p)
        data["macd_line"] = macd_df["macd_line"]
        data["macd_signal"] = macd_df["macd_signal"]
        data["macd_hist"] = macd_df["macd_hist"]

        data["ema_trend"] = compute_ema(data["close"], period=trend_p)
        data["vol_sma"] = compute_sma(data["volume"], period=vol_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)

        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. MACD line crosses above signal line
        2. Close > EMA 200
        3. Volume > vol_sma * vol_factor
        """
        vol_fact = self.parameters.get("vol_factor", 1.3)

        prev_macd_below = df["macd_line"].shift(1) <= df["macd_signal"].shift(1)
        curr_macd_above = df["macd_line"] > df["macd_signal"]
        macd_cross_up = prev_macd_below & curr_macd_above

        trend_condition = df["close"] > df["ema_trend"]
        volume_condition = df["volume"] > (df["vol_sma"] * vol_fact)

        entry_signal = (macd_cross_up & trend_condition & volume_condition).astype(int)
        return entry_signal

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        MACD line crosses below signal line.
        """
        prev_macd_above = df["macd_line"].shift(1) >= df["macd_signal"].shift(1)
        curr_macd_below = df["macd_line"] < df["macd_signal"]
        macd_cross_down = prev_macd_above & curr_macd_below

        return macd_cross_down.astype(int)
