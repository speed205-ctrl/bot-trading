"""Calculates commissions and slippage costs."""
from dataclasses import dataclass


@dataclass
class CostConfig:
    commission_rate: float = 0.0004  # 0.04%
    slippage_pct: float = 0.0005     # 0.05%


class CostCalculator:
    """Computes execution prices with slippage and trading fees."""

    def __init__(self, config: CostConfig = CostConfig()):
        self.config = config

    def apply_entry_slippage(self, price: float, direction: str = "long") -> float:
        """Applies slippage to entry price. For long, pays slightly more."""
        if direction == "long":
            return price * (1.0 + self.config.slippage_pct)
        return price * (1.0 - self.config.slippage_pct)

    def apply_exit_slippage(self, price: float, direction: str = "long") -> float:
        """Applies slippage to exit price. For long, sells slightly lower."""
        if direction == "long":
            return price * (1.0 - self.config.slippage_pct)
        return price * (1.0 + self.config.slippage_pct)

    def calculate_commission(self, notional_value: float) -> float:
        """Calculates exchange trading commission on notional volume."""
        return abs(notional_value) * self.config.commission_rate
