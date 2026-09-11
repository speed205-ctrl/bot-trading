"""Unified metrics calculator and criteria evaluation."""
from typing import Any, Dict

from src.backtest.engine import BacktestResult
from src.metrics.performance_metrics import calculate_performance_metrics
from src.metrics.risk_metrics import calculate_risk_metrics
from src.metrics.trade_statistics import calculate_trade_statistics


def calculate_all_metrics(result: BacktestResult, period_type: str = "in_sample") -> Dict[str, Any]:
    """Calculates all performance, risk, and trade metrics, and evaluates Section 8 acceptance criteria."""
    start_time = result.equity_curve.index.min()
    end_time = result.equity_curve.index.max()

    perf = calculate_performance_metrics(result.initial_capital, result.equity_curve, result.trades)
    risk = calculate_risk_metrics(result.equity_curve, result.trades)
    stats = calculate_trade_statistics(result.trades, start_time, end_time, result.initial_capital)

    all_metrics = {**perf, **risk, **stats}

    # Warnings per spec Section 4.5
    warnings = []
    if all_metrics["total_trades"] < 30:
        warnings.append("Muestra insuficiente (< 30 operaciones)")
    if all_metrics["profit_factor"] < 1.0:
        warnings.append("Estrategia perdedora (Profit Factor < 1.0)")
    if all_metrics["max_drawdown_pct"] > 0.30:
        warnings.append("Alto riesgo (Drawdown > 30%)")

    # Criteria checks per Section 8
    criteria = {}
    if period_type.lower() == "in_sample":
        criteria["profit_factor_gt_1_3"] = all_metrics["profit_factor"] > 1.3
        criteria["max_drawdown_lt_20pct"] = all_metrics["max_drawdown_pct"] < 0.20
        criteria["win_rate_gt_40pct"] = all_metrics["win_rate_pct"] > 0.40
        criteria["total_trades_gt_100"] = all_metrics["total_trades"] > 100
        criteria["sharpe_gt_1_0"] = all_metrics["sharpe_ratio"] > 1.0
        criteria["total_return_positive"] = all_metrics["total_return_pct"] > 0.0
    else:  # out_of_sample
        criteria["profit_factor_gt_1_1"] = all_metrics["profit_factor"] > 1.1
        criteria["max_drawdown_lt_25pct"] = all_metrics["max_drawdown_pct"] < 0.25
        criteria["win_rate_gt_35pct"] = all_metrics["win_rate_pct"] > 0.35
        criteria["total_trades_gt_30"] = all_metrics["total_trades"] > 30
        criteria["sharpe_gt_0_8"] = all_metrics["sharpe_ratio"] > 0.8
        criteria["total_return_positive"] = all_metrics["total_return_pct"] > 0.0

    passed_all = all(criteria.values())

    return {
        "strategy_name": result.strategy_name,
        "risk_profile": result.risk_profile_name,
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "period_type": period_type,
        "metrics": all_metrics,
        "warnings": warnings,
        "criteria": criteria,
        "verdict": "PASA" if passed_all else "NO PASA",
    }
