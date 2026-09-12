"""Risk Guard and Circuit Breakers for real-time live trading bot."""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from src.backtest.position_manager import PRESET_PROFILES, RiskProfile
from src.bot.state_manager import StateManager
from src.utils.logger import setup_logger

logger = setup_logger("RiskGuard")


class RiskGuard:
    """Enforces institutional risk management rules and circuit breakers in real time."""

    def __init__(
        self,
        risk_profile: str = "moderate",
        state_manager: Optional[StateManager] = None,
        base_capital: float = 10000.0
    ):
        self.profile: RiskProfile = PRESET_PROFILES.get(risk_profile.lower(), PRESET_PROFILES["moderate"])
        self.state_manager = state_manager or StateManager()
        self.base_capital = base_capital
        self._manual_lockout: bool = False
        self._lockout_reason: str = ""

    @property
    def is_locked(self) -> bool:
        return self._manual_lockout

    def trigger_kill_switch(self, reason: str = "Intervención de emergencia (Panic Button)"):
        """Locks the bot from executing any new orders."""
        self._manual_lockout = True
        self._lockout_reason = reason
        logger.warning(f"[KILL SWITCH ACTIVADO] {reason}")

    def reset_kill_switch(self):
        """Unlocks the bot."""
        self._manual_lockout = False
        self._lockout_reason = ""
        logger.info("[KILL SWITCH DESACTIVADO] Bot reanudado.")

    def check_daily_circuit_breaker(self, current_capital: Optional[float] = None) -> Tuple[bool, str]:
        """Checks if today's accumulated losses exceed the maximum daily drawdown threshold."""
        if self._manual_lockout:
            return True, f"Bot bloqueado manualmente: {self._lockout_reason}"

        capital = current_capital or self.base_capital
        daily_stats = self.state_manager.get_daily_pnl()
        daily_net_pnl = daily_stats["total_net_pnl"]

        # Calculate daily drawdown percentage
        daily_loss_pct = abs(daily_net_pnl) / capital if daily_net_pnl < 0 else 0.0
        max_allowed_dd = self.profile.max_daily_drawdown_pct

        if daily_loss_pct >= max_allowed_dd:
            reason = (
                f"CIRCUIT BREAKER DISPARADO: Pérdida acumulada del día ${daily_net_pnl:,.2f} "
                f"({daily_loss_pct*100:.1f}%) supera el límite diario de {max_allowed_dd*100:.1f}%."
            )
            logger.error(f"🚨 {reason}")
            return True, reason

        return False, "Riesgo diario dentro de límites tolerables."

    def validate_new_order(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        current_capital: Optional[float] = None
    ) -> Tuple[bool, str, float]:
        """Validates all risk constraints before allowing a new entry order.
        
        Returns:
            (allowed: bool, reason: str, position_size: float)
        """
        # 1. Circuit breaker check
        tripped, reason = self.check_daily_circuit_breaker(current_capital)
        if tripped:
            return False, reason, 0.0

        # 2. Position count check
        active_positions = self.state_manager.get_all_active_positions()
        if len(active_positions) >= self.profile.max_open_positions:
            msg = f"Límite alcanzado: Máximo de {self.profile.max_open_positions} posiciones abiertas simultáneas."
            logger.warning(msg)
            return False, msg, 0.0

        # 3. Duplicate symbol check
        if any(p["symbol"] == symbol for p in active_positions):
            msg = f"Ya existe una posición abierta en {symbol}."
            logger.warning(msg)
            return False, msg, 0.0

        # 4. Sizing validation
        capital = current_capital or self.base_capital
        sl_distance = abs(entry_price - stop_loss_price)
        if sl_distance <= 0:
            return False, "Distancia de Stop Loss inválida (cero o negativa).", 0.0

        risk_amount = capital * self.profile.risk_per_trade_pct
        size = risk_amount / sl_distance

        # Max leverage guard
        notional_value = size * entry_price
        max_notional = capital * self.profile.max_leverage
        if notional_value > max_notional:
            size = max_notional / entry_price
            logger.info(f"Tamaño ajustado por apalancamiento máximo {self.profile.max_leverage}x -> {size:.4f}")

        if size <= 0:
            return False, "Tamaño de posición calculado es 0.", 0.0

        return True, "Orden autorizada por RiskGuard.", size
