"""Strategy 3: Breakout de Bandas de Bollinger."""
from typing import Any, Dict, Optional
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.strategies.indicators import compute_atr, compute_bollinger_bands, compute_sma


class BollingerBreakoutStrategy(BaseStrategy):
    """Volatility breakout strategy triggered after Bollinger Band compression with volume surge."""

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        default_params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "vol_factor": 1.5,
            "squeeze_threshold": 1.5,  # Bandwidth % threshold (< 1.5% considered squeeze)
            "bandwidth_tp_mult": 2.0,
            "vol_sma_period": 20,
            "atr_period": 14,
            "atr_sl_mult": 2.0,
        }
        if parameters:
            default_params.update(parameters)

        param_ranges = {
            "bb_period": [14, 20, 25, 30],
            "bb_std": [1.5, 2.0, 2.5, 3.0],
            "vol_factor": [1.2, 1.5, 2.0, 2.5],
            "squeeze_threshold": [1.0, 1.5, 2.0, 2.5],
            "bandwidth_tp_mult": [1.5, 2.0, 2.5, 3.0],
        }

        super().__init__(
            name="Breakout de Bandas de Bollinger",
            description="Ruptura de volatilidad sobre la banda superior tras compresión de bandas con volumen anormal.",
            preferred_timeframe="1h",
            direction="long_only",
            parameters=default_params,
            param_ranges=param_ranges,
            indicators_required=["bollinger_bands", "volume_sma", "atr_14"],
        )

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        bb_p = self.parameters.get("bb_period", 20)
        bb_std = self.parameters.get("bb_std", 2.0)
        vol_p = self.parameters.get("vol_sma_period", 20)
        atr_p = self.parameters.get("atr_period", 14)

        bb_df = compute_bollinger_bands(data["close"], period=bb_p, std_dev=bb_std)
        data["bb_middle"] = bb_df["bb_middle"]
        data["bb_upper"] = bb_df["bb_upper"]
        data["bb_lower"] = bb_df["bb_lower"]
        data["bb_bandwidth"] = bb_df["bb_bandwidth"] * 100.0  # Normalized to percentage

        data["vol_sma"] = compute_sma(data["volume"], period=vol_p)
        data["atr"] = compute_atr(data["high"], data["low"], data["close"], period=atr_p)

        return data

    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Entry rules:
        1. Close > Upper Bollinger Band
        2. Bandwidth was compressed before breakout (previous candle bandwidth < squeeze_threshold)
        3. Volume > vol_sma * vol_factor
        """
        squeeze_th = self.parameters.get("squeeze_threshold", 1.5)
        vol_fact = self.parameters.get("vol_factor", 1.5)

        breakout_up = df["close"] > df["bb_upper"]
        was_squeezed = df["bb_bandwidth"].shift(1) < squeeze_th
        volume_surge = df["volume"] > (df["vol_sma"] * vol_fact)

        entry_signal = (breakout_up & was_squeezed & volume_surge).astype(int)
        return entry_signal

    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Exit rules:
        Close falls below Middle Bollinger Band.
        """
        cross_below_middle = (df["close"].shift(1) >= df["bb_middle"].shift(1)) & (df["close"] < df["bb_middle"])
        return cross_below_middle.astype(int)

    def get_take_profit(self, entry_price: float, atr_value: float, current_row: pd.Series) -> float:
        """Take profit based on bandwidth width or ATR multiple."""
        bw_mult = self.parameters.get("bandwidth_tp_mult", 2.0)
        upper = current_row.get("bb_upper", entry_price + 2.0 * atr_value)
        lower = current_row.get("bb_lower", entry_price - 2.0 * atr_value)
        band_height = abs(upper - lower)
        return entry_price + (bw_mult * band_height) if band_height > 0 else entry_price + (3.0 * atr_value)
