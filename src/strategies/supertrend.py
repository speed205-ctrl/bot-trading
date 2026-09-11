"""Strategy 6: Supertrend con Confirmación de Volumen."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_sma, compute_supertrend


class SupertrendStrategy(BaseStrategy):
    """Adaptive trend-following strategy using Supertrend bands filtered by volume."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "st_period": 10,
            "st_multiplier": 3.0,
            "vol_sma_period": 20,
            "vol_factor": 1.1,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.5,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "st_period": [7, 10, 14],
            "st_multiplier": [2.0, 2.5, 3.0, 3.5],
            "vol_factor": [1.0, 1.2, 1.5],
            "atr_sl_mult": [1.5, 2.0, 2.5],
            "atr_tp_mult": [2.5, 3.5, 4.5],
        }

        super().__init__(
            name="Supertrend con Confirmación de Volumen",
            description="Seguimiento de tendencia adaptativo con bandas dinámicas por ATR y confirmación de volumen.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["supertrend", "volume_sma", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        p = self.parameters.get("st_period", 10)
        mult = self.parameters.get("st_multiplier", 3.0)
        vol_p = self.parameters.get("vol_sma_period", 20)
        atr_p = self.parameters.get("atr_period", 14)

        st_df = compute_supertrend(data["high"], data["low"], data["close"], period=p, multiplier=mult)
        data["supertrend"] = st_df["supertrend"]
        data["st_direction"] = st_df["supertrend_direction"]
        data["st_lower"] = st_df["supertrend_lower"]
        data["st_upper"] = st_df["supertrend_upper"]

        data["vol_sma"] = compute_sma(data["volume"], period=vol_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)
        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Supertrend flips from bearish (-1) to bullish (1)
        2. Volume > vol_sma * vol_factor
        """
        vol_fact = self.parameters.get("vol_factor", 1.1)

        prev_bearish = df["st_direction"].shift(1) == -1
        curr_bullish = df["st_direction"] == 1
        st_flip_up = prev_bearish & curr_bullish

        volume_ok = df["volume"] > (df["vol_sma"] * vol_fact)
        entry_signal = (st_flip_up & volume_ok).astype(int)
        return entry_signal

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Supertrend flips back to bearish (-1).
        """
        st_flip_down = (df["st_direction"].shift(1) == 1) & (df["st_direction"] == -1)
        return st_flip_down.astype(int)

    def get_stop_loss(self, entry_price: float, atr_value: float, current_row: pd.Series) -> float:
        """Uses the Supertrend lower band or ATR stop."""
        st_lower = current_row.get("st_lower", entry_price - 2.0 * atr_value)
        atr_sl = entry_price - (self.parameters.get("atr_sl_mult", 2.0) * atr_value)
        return max(st_lower, atr_sl)
