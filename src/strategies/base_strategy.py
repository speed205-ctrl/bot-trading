"""Abstract base class for all trading strategies."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import pandas as pd


class BaseStrategy(ABC):
    """Base strategy framework interface."""

    def __init__(
        self,
        name: str,
        description: str,
        preferred_timeframe: str = "1h",
        direction: str = "long_only",
        parameters: Optional[Dict[str, Any]] = None,
        param_ranges: Optional[Dict[str, List[Any]]] = None,
        indicators_required: Optional[List[str]] = None
    ):
        self.name = name
        self.description = description
        self.preferred_timeframe = preferred_timeframe
        self.direction = direction
        self.parameters = parameters or {}
        self.param_ranges = param_ranges or {}
        self.indicators_required = indicators_required or []

    def set_parameters(self, new_params: Dict[str, Any]) -> None:
        """Updates strategy parameters."""
        self.parameters.update(new_params)

    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates all indicators and returns a new DataFrame without mutating the input."""
        pass

    @abstractmethod
    def generate_entry_signals(self, df: pd.DataFrame) -> pd.Series:
        """Generates binary entry signals: 1 for Buy/Long entry, 0 otherwise."""
        pass

    @abstractmethod
    def generate_exit_signals(self, df: pd.DataFrame) -> pd.Series:
        """Generates binary exit signals: 1 for Exit, 0 otherwise."""
        pass

    def get_stop_loss(self, entry_price: float, atr_value: float, current_row: pd.Series) -> float:
        """Calculates stop-loss price level for a position."""
        sl_mult = self.parameters.get("atr_sl_mult", 2.0)
        return entry_price - (sl_mult * atr_value)

    def get_take_profit(self, entry_price: float, atr_value: float, current_row: pd.Series) -> float:
        """Calculates take-profit price level for a position."""
        tp_mult = self.parameters.get("atr_tp_mult", 3.0)
        return entry_price + (tp_mult * atr_value)

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepares dataset by calculating indicators and generating signals.

        Guarantees input is never mutated.
        """
        data = self.calculate_indicators(df.copy())
        data["entry_signal"] = self.generate_entry_signals(data)
        data["exit_signal"] = self.generate_exit_signals(data)
        return data

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', timeframe='{self.preferred_timeframe}', params={self.parameters})>"
