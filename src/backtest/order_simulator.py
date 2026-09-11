"""Simulates order execution with slippage and intra-bar price action."""
from dataclasses import dataclass
from typing import Optional, Tuple
import pandas as pd

from src.backtest.cost_calculator import CostCalculator
from src.backtest.position_manager import Position


@dataclass
class Trade:
    symbol: str
    direction: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    size: float
    notional: float
    gross_pnl: float
    net_pnl: float
    total_commission: float
    total_slippage_cost: float
    return_pct: float
    exit_reason: str  # 'stop_loss', 'take_profit', 'signal_exit', 'margin_stop'
    duration_hours: float


class OrderSimulator:
    """Simulates realistic order execution for backtesting."""

    def __init__(self, cost_calculator: Optional[CostCalculator] = None):
        self.costs = cost_calculator or CostCalculator()

    def execute_entry(
        self,
        symbol: str,
        direction: str,
        open_price: float,
        size: float,
        timestamp: pd.Timestamp,
        stop_loss: float,
        take_profit: float,
        leverage: int,
        risk_profile_name: str
    ) -> Tuple[Position, float]:
        """Executes entry order at candle open with slippage and returns (Position, commission_paid)."""
        actual_price = self.costs.apply_entry_slippage(open_price, direction)
        notional = actual_price * size
        margin = notional / leverage
        commission = self.costs.calculate_commission(notional)

        position = Position(
            symbol=symbol,
            direction=direction,
            entry_time=timestamp,
            entry_price=actual_price,
            size=size,
            notional=notional,
            margin=margin,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_profile=risk_profile_name
        )
        return position, commission

    def check_position_exit(
        self,
        position: Position,
        candle: pd.Series,
        timestamp: pd.Timestamp,
        signal_exit_active: bool = False
    ) -> Optional[Trade]:
        """Evaluates whether an open position should be closed during the current candle.

        Priority order:
        1. Stop loss hit within candle [low <= stop_loss]
        2. Take profit hit within candle [high >= take_profit]
        3. Strategy signal exit at candle open
        """
        open_p = candle["open"]
        high_p = candle["high"]
        low_p = candle["low"]

        exit_triggered = False
        raw_exit_price = 0.0
        reason = ""

        # Check intra-bar Stop Loss and Take Profit
        sl_hit = low_p <= position.stop_loss
        tp_hit = high_p >= position.take_profit

        if sl_hit and tp_hit:
            # Conservative assumption: SL was hit first
            exit_triggered = True
            raw_exit_price = position.stop_loss
            reason = "stop_loss"
        elif sl_hit:
            exit_triggered = True
            raw_exit_price = position.stop_loss
            reason = "stop_loss"
        elif tp_hit:
            exit_triggered = True
            raw_exit_price = position.take_profit
            reason = "take_profit"
        elif signal_exit_active:
            # Signal generated on previous bar, exit at current bar's open
            exit_triggered = True
            raw_exit_price = open_p
            reason = "signal_exit"

        if not exit_triggered:
            return None

        # Apply slippage on exit
        exec_exit_price = self.costs.apply_exit_slippage(raw_exit_price, position.direction)
        exit_notional = exec_exit_price * position.size
        entry_commission = self.costs.calculate_commission(position.notional)
        exit_commission = self.costs.calculate_commission(exit_notional)
        total_commission = entry_commission + exit_commission

        # Slippage cost estimation
        ideal_pnl = (raw_exit_price - position.entry_price) * position.size
        gross_pnl = (exec_exit_price - position.entry_price) * position.size
        slippage_cost = abs(ideal_pnl - gross_pnl)
        net_pnl = gross_pnl - total_commission

        return_pct = net_pnl / position.margin if position.margin > 0 else 0.0
        duration_hours = max((timestamp - position.entry_time).total_seconds() / 3600.0, 1.0)

        return Trade(
            symbol=position.symbol,
            direction=position.direction,
            entry_time=position.entry_time,
            exit_time=timestamp,
            entry_price=position.entry_price,
            exit_price=exec_exit_price,
            size=position.size,
            notional=exit_notional,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            total_commission=total_commission,
            total_slippage_cost=slippage_cost,
            return_pct=return_pct,
            exit_reason=reason,
            duration_hours=duration_hours
        )
