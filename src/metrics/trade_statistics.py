"""Calculates trade logs statistics, durations, and cost breakdowns."""
from typing import Dict, List
import numpy as np
import pandas as pd

from src.backtest.order_simulator import Trade
from src.utils.helpers import safe_div


def calculate_trade_statistics(
    trades: List[Trade],
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    initial_capital: float = 10000.0
) -> Dict[str, float]:
    """Calculates operational trade statistics and execution cost totals."""
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate_pct": 0.0,
            "loss_rate_pct": 0.0,
            "avg_trade_duration_hours": 0.0,
            "max_trade_duration_hours": 0.0,
            "trades_per_week": 0.0,
            "total_commissions": 0.0,
            "total_slippage": 0.0,
            "cost_impact_pct": 0.0,
        }

    winning = [t for t in trades if t.net_pnl > 0]
    losing = [t for t in trades if t.net_pnl < 0]

    win_rate = len(winning) / total_trades
    loss_rate = len(losing) / total_trades

    durations = [t.duration_hours for t in trades]
    avg_duration = float(np.mean(durations)) if durations else 0.0
    max_duration = float(np.max(durations)) if durations else 0.0

    days = max((end_time - start_time).total_seconds() / 86400.0, 1.0)
    weeks = max(days / 7.0, 1.0)
    trades_per_week = total_trades / weeks

    total_commissions = sum(t.total_commission for t in trades)
    total_slippage = sum(t.total_slippage_cost for t in trades)
    cost_impact = (total_commissions + total_slippage) / initial_capital if initial_capital > 0 else 0.0

    return {
        "total_trades": total_trades,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate_pct": win_rate,
        "loss_rate_pct": loss_rate,
        "avg_trade_duration_hours": avg_duration,
        "max_trade_duration_hours": max_duration,
        "trades_per_week": trades_per_week,
        "total_commissions": total_commissions,
        "total_slippage": total_slippage,
        "cost_impact_pct": cost_impact,
    }
