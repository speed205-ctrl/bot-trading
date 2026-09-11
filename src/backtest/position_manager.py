"""Position sizing and risk management per risk profile."""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class RiskProfile:
    name: str
    risk_per_trade_pct: float
    max_leverage: int
    margin_type: str = "isolated"
    max_open_positions: int = 1
    max_daily_drawdown_pct: float = 0.05
    max_total_drawdown_pct: float = 0.20


# Pre-configured risk profiles per spec
PRESET_PROFILES: Dict[str, RiskProfile] = {
    "conservative": RiskProfile(
        name="Perfil Conservador",
        risk_per_trade_pct=0.01,
        max_leverage=5,
        margin_type="isolated",
        max_open_positions=1,
        max_daily_drawdown_pct=0.03,
        max_total_drawdown_pct=0.15,
    ),
    "moderate": RiskProfile(
        name="Perfil Moderado",
        risk_per_trade_pct=0.02,
        max_leverage=10,
        margin_type="isolated",
        max_open_positions=1,
        max_daily_drawdown_pct=0.05,
        max_total_drawdown_pct=0.20,
    ),
    "aggressive": RiskProfile(
        name="Perfil Agresivo",
        risk_per_trade_pct=0.04,
        max_leverage=20,
        margin_type="isolated",
        max_open_positions=2,
        max_daily_drawdown_pct=0.08,
        max_total_drawdown_pct=0.30,
    ),
}


@dataclass
class Position:
    symbol: str
    direction: str
    entry_time: any
    entry_price: float
    size: float  # Quantity of asset
    notional: float  # size * entry_price
    margin: float  # notional / leverage
    leverage: int
    stop_loss: float
    take_profit: float
    risk_profile: str


class PositionManager:
    """Manages position sizing, margin limits, and position tracking."""

    def __init__(self, profile: Optional[RiskProfile] = None):
        self.profile = profile or PRESET_PROFILES["moderate"]
        self.open_positions: Dict[str, Position] = {}

    @property
    def current_open_count(self) -> int:
        return len(self.open_positions)

    def can_open_position(self, symbol: str) -> bool:
        """Checks if a new position can be opened."""
        if symbol in self.open_positions:
            return False  # Max 1 position per symbol at a time
        if self.current_open_count >= self.profile.max_open_positions:
            return False
        return True

    def calculate_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_loss_price: float,
        leverage: Optional[int] = None
    ) -> float:
        """Calculates position size (quantity in units) based on ATR distance and risk profile.

        Formula: size = (capital * risk_pct) / abs(entry_price - stop_loss_price)
        Capped by maximum leverage and available capital.
        """
        if capital <= 0 or entry_price <= 0:
            return 0.0

        sl_distance = abs(entry_price - stop_loss_price)
        if sl_distance <= 0:
            return 0.0

        risk_amount = capital * self.profile.risk_per_trade_pct
        size = risk_amount / sl_distance

        used_leverage = leverage or self.profile.max_leverage
        max_notional = capital * used_leverage
        position_notional = size * entry_price

        # Cap size if notional exceeds leverage limit
        if position_notional > max_notional:
            size = max_notional / entry_price

        return size
