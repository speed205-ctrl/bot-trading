"""Strategy 11: Cinta de Medias Móviles Triples (Triple EMA Ribbon)."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_ema


class TripleEmaRibbonStrategy(BaseStrategy):
    """Trend-following strategy exploiting alignment across short, medium, and long EMAs with pullback entries."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "ema_fast": 8,
            "ema_medium": 21,
            "ema_slow": 55,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
            "atr_tp_mult": 3.5,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "ema_fast": [5, 8, 10],
            "ema_medium": [18, 21, 25],
            "ema_slow": [50, 55, 60],
            "atr_sl_mult": [1.5, 2.0, 2.5],
            "atr_tp_mult": [2.5, 3.5, 4.5],
        }

        super().__init__(
            name="Cinta de Medias Triples (Ribbon)",
            description="Alineación tendencial 8-21-55 EMA con entradas en retroceso a la media intermedia (21).",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["ema_8", "ema_21", "ema_55", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        fast_p = self.parameters.get("ema_fast", 8)
        med_p = self.parameters.get("ema_medium", 21)
        slow_p = self.parameters.get("ema_slow", 55)
        atr_p = self.parameters.get("atr_period", 14)

        data["ema_fast"] = compute_ema(data["close"], period=fast_p)
        data["ema_medium"] = compute_ema(data["close"], period=med_p)
        data["ema_slow"] = compute_ema(data["close"], period=slow_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)
        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Ribbon alignment: Fast > Medium > Slow
        2. Pullback: Low touched or dipped near Medium EMA, but Close closed above it
        """
        ribbon_aligned = (df["ema_fast"] > df["ema_medium"]) & (df["ema_medium"] > df["ema_slow"])
        pullback_touched = df["low"] <= df["ema_medium"]
        closed_above = df["close"] > df["ema_medium"]

        return (ribbon_aligned & pullback_touched & closed_above).astype(int)

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Fast EMA crosses below Medium EMA.
        """
        cross_down = (df["ema_fast"].shift(1) >= df["ema_medium"].shift(1)) & (df["ema_fast"] < df["ema_medium"])
        return cross_down.astype(int)
