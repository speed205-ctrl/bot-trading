"""Grid search parameter optimizer for trading strategies."""
import itertools
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.backtest.engine import BacktestEngine, BacktestResult
from src.metrics import calculate_all_metrics
from src.strategies.base_strategy import BaseStrategy
from src.utils.logger import setup_logger

logger = setup_logger("GridSearch")


@dataclass
class OptimizationResult:
    parameters: Dict[str, Any]
    target_value: float
    total_trades: int
    profit_factor: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_return_pct: float
    win_rate_pct: float
    backtest_result: BacktestResult


class GridSearchOptimizer:
    """Explores grid of parameter combinations over In-Sample data."""

    def __init__(
        self,
        target_metric: str = "profit_factor",
        max_combinations: int = 100,
        min_trades: int = 30,
        initial_capital: float = 10000.0,
        risk_profile: str = "moderate"
    ):
        self.target_metric = target_metric
        self.max_combinations = max_combinations
        self.min_trades = min_trades
        self.initial_capital = initial_capital
        self.risk_profile = risk_profile

    def _generate_param_combinations(self, param_ranges: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Generates Cartesian product of all parameter ranges."""
        keys = list(param_ranges.keys())
        values = list(param_ranges.values())
        combos = []

        for combination in itertools.product(*values):
            combos.append(dict(zip(keys, combination)))

        if len(combos) > self.max_combinations:
            logger.info(f"Grid size ({len(combos)}) exceeds max_combinations ({self.max_combinations}). Capping grid.")
            combos = combos[:self.max_combinations]

        return combos

    def optimize(
        self,
        strategy_class: Any,
        df: pd.DataFrame,
        param_ranges: Optional[Dict[str, List[Any]]] = None,
        symbol: str = "BTC/USDT"
    ) -> List[OptimizationResult]:
        """Runs backtest over all parameter combinations and returns ranked list of valid results."""
        dummy_strat = strategy_class()
        ranges = param_ranges or dummy_strat.param_ranges
        combinations = self._generate_param_combinations(ranges)

        logger.info(f"Starting Grid Search for '{dummy_strat.name}' with {len(combinations)} combinations...")
        engine = BacktestEngine(initial_capital=self.initial_capital, risk_profile=self.risk_profile)
        results: List[OptimizationResult] = []

        for idx, params in enumerate(combinations, 1):
            strat_instance = strategy_class(parameters=params)
            res = engine.run(strat_instance, df, symbol=symbol)
            metrics_data = calculate_all_metrics(res, period_type="in_sample")
            m = metrics_data["metrics"]

            # Filter out combinations with fewer than min_trades (30)
            if m["total_trades"] < self.min_trades:
                continue

            target_val = float(m.get(self.target_metric, 0.0))
            results.append(OptimizationResult(
                parameters=params,
                target_value=target_val,
                total_trades=int(m["total_trades"]),
                profit_factor=float(m["profit_factor"]),
                sharpe_ratio=float(m["sharpe_ratio"]),
                max_drawdown_pct=float(m["max_drawdown_pct"]),
                total_return_pct=float(m["total_return_pct"]),
                win_rate_pct=float(m["win_rate_pct"]),
                backtest_result=res
            ))

        # Sort descending by target metric
        results.sort(key=lambda r: r.target_value, reverse=True)
        logger.info(f"Grid Search finished. {len(results)} valid configurations met the min {self.min_trades} trades requirement.")
        return results
