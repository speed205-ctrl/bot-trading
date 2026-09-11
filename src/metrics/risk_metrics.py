"""Calculates risk, drawdown, volatility, and downside statistics."""
from typing import Dict, List
import numpy as np
import pandas as pd

from src.backtest.order_simulator import Trade


def calculate_risk_metrics(
    equity_curve: pd.DataFrame,
    trades: List[Trade]
) -> Dict[str, float]:
    """Calculates risk and drawdown metrics."""
    if equity_curve.empty:
        return {
            "max_drawdown_pct": 0.0,
            "max_drawdown_abs": 0.0,
            "drawdown_duration_days": 0.0,
            "annualized_volatility": 0.0,
            "var_95_daily": 0.0,
            "max_consecutive_losses": 0,
        }

    equity = equity_curve["equity"]
    peak = equity.cummax()
    dd_abs = peak - equity
    dd_pct = dd_abs / peak.replace(0, np.nan)

    max_dd_pct = float(dd_pct.max()) if not dd_pct.empty else 0.0
    max_dd_abs = float(dd_abs.max()) if not dd_abs.empty else 0.0

    # Drawdown duration: length of time spent below high water mark
    is_in_dd = dd_abs > 0
    dd_duration_days = 0.0
    if is_in_dd.any():
        # Identify consecutive streaks of being in drawdown
        streak_groups = (~is_in_dd).cumsum()
        dd_streaks = is_in_dd.groupby(streak_groups).sum()
        # Since samples are hourly, duration in days = max hours / 24.0
        max_dd_hours = float(dd_streaks.max())
        dd_duration_days = max_dd_hours / 24.0

    # Daily returns volatility and VaR (95%)
    daily_equity = equity.resample("1D").last().dropna()
    daily_returns = daily_equity.pct_change().dropna()

    if len(daily_returns) > 1:
        ann_volatility = float(daily_returns.std() * np.sqrt(365.0))
        var_95 = float(np.percentile(daily_returns, 5))
    else:
        ann_volatility = 0.0
        var_95 = 0.0

    # Max consecutive losses from closed trades
    max_losses = 0
    current_losses = 0
    for t in trades:
        if t.net_pnl < 0:
            current_losses += 1
            max_losses = max(max_losses, current_losses)
        else:
            current_losses = 0

    return {
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_abs": max_dd_abs,
        "drawdown_duration_days": dd_duration_days,
        "annualized_volatility": ann_volatility,
        "var_95_daily": var_95,
        "max_consecutive_losses": max_losses,
    }
