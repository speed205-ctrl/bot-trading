"""Calculates financial performance and return metrics."""
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.backtest.order_simulator import Trade
from src.utils.helpers import safe_div


def calculate_performance_metrics(
    initial_capital: float,
    equity_curve: pd.DataFrame,
    trades: List[Trade]
) -> Dict[str, float]:
    """Calculates return and performance metrics."""
    if equity_curve.empty:
        return {
            "initial_capital": initial_capital,
            "final_equity": initial_capital,
            "total_return_pct": 0.0,
            "annualized_return_pct": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "risk_reward_ratio": 0.0,
        }

    final_equity = float(equity_curve["equity"].iloc[-1])
    total_return = (final_equity - initial_capital) / initial_capital

    # Time span in days
    start_time = equity_curve.index.min()
    end_time = equity_curve.index.max()
    days = max((end_time - start_time).total_seconds() / 86400.0, 1.0)

    # Annualized return (compound)
    if total_return > -1.0:
        annualized_return = ((1.0 + total_return) ** (365.25 / days)) - 1.0
    else:
        annualized_return = -1.0

    # Daily returns for Sharpe and Sortino
    daily_equity = equity_curve["equity"].resample("1D").last().dropna()
    daily_returns = daily_equity.pct_change().dropna()

    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365.0)
    else:
        sharpe = 0.0

    downside_returns = daily_returns[daily_returns < 0]
    if len(downside_returns) > 1 and downside_returns.std() > 0:
        sortino = (daily_returns.mean() / downside_returns.std()) * np.sqrt(365.0)
    else:
        sortino = sharpe

    # Max Drawdown for Calmar
    peak = equity_curve["equity"].cummax()
    dd_series = (peak - equity_curve["equity"]) / peak
    max_dd = float(dd_series.max()) if not dd_series.empty else 0.0
    calmar = safe_div(annualized_return, max_dd, default=0.0)

    # Trade statistics
    winning_trades = [t.net_pnl for t in trades if t.net_pnl > 0]
    losing_trades = [abs(t.net_pnl) for t in trades if t.net_pnl < 0]

    gross_profit = sum(winning_trades)
    gross_loss = sum(losing_trades)

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = 99.9  # High positive cap
    else:
        profit_factor = 0.0

    avg_win = float(np.mean(winning_trades)) if winning_trades else 0.0
    avg_loss = float(np.mean(losing_trades)) if losing_trades else 0.0
    risk_reward = safe_div(avg_win, avg_loss, default=0.0)

    return {
        "initial_capital": initial_capital,
        "final_equity": final_equity,
        "total_return_pct": total_return,
        "annualized_return_pct": annualized_return,
        "profit_factor": profit_factor,
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "calmar_ratio": float(calmar),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "risk_reward_ratio": risk_reward,
    }
