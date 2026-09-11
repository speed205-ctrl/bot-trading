"""Walk-Forward rolling window analysis."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pandas as pd
from dateutil.relativedelta import relativedelta

from src.backtest.engine import BacktestEngine, BacktestResult
from src.metrics import calculate_all_metrics
from src.optimizer.grid_search import GridSearchOptimizer
from src.utils.logger import setup_logger

logger = setup_logger("WalkForward")


@dataclass
class WalkForwardWindow:
    window_index: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    best_params: Dict[str, Any]
    train_profit_factor: float
    test_profit_factor: float
    test_trades: int
    test_return_pct: float
    test_max_drawdown_pct: float
    passed: bool


class WalkForwardAnalyzer:
    """Executes rolling Walk-Forward optimization and out-of-sample validation."""

    def __init__(
        self,
        train_months: int = 6,
        test_months: int = 2,
        step_months: int = 2,
        initial_capital: float = 10000.0,
        risk_profile: str = "moderate"
    ):
        self.train_months = train_months
        self.test_months = test_months
        self.step_months = step_months
        self.initial_capital = initial_capital
        self.risk_profile = risk_profile

    def run(
        self,
        strategy_class: Any,
        df: pd.DataFrame,
        symbol: str = "BTC/USDT",
        max_optim_combos: int = 30
    ) -> List[WalkForwardWindow]:
        """Runs rolling walk-forward analysis on full historical dataset."""
        if df.empty:
            raise ValueError("Dataset is empty, cannot execute Walk-Forward.")

        start_date = df.index.min()
        end_date = df.index.max()
        current_train_start = start_date
        windows: List[WalkForwardWindow] = []
        window_idx = 1

        optimizer = GridSearchOptimizer(
            target_metric="profit_factor",
            max_combinations=max_optim_combos,
            min_trades=5,  # lower threshold for shorter windows
            initial_capital=self.initial_capital,
            risk_profile=self.risk_profile
        )
        engine = BacktestEngine(initial_capital=self.initial_capital, risk_profile=self.risk_profile)

        while True:
            train_end = current_train_start + relativedelta(months=self.train_months)
            test_start = train_end
            test_end = test_start + relativedelta(months=self.test_months)

            if test_end > end_date:
                break

            train_df = df[(df.index >= current_train_start) & (df.index < train_end)]
            test_df = df[(df.index >= test_start) & (df.index <= test_end)]

            if len(train_df) < 50 or len(test_df) < 20:
                break

            logger.info(f"Walk-Forward Window {window_idx}: Train [{current_train_start.date()} to {train_end.date()}], Test [{test_start.date()} to {test_end.date()}]")

            # 1. Optimize on training window
            optim_results = optimizer.optimize(strategy_class, train_df, symbol=symbol)
            if not optim_results:
                best_params = strategy_class().parameters
                train_pf = 1.0
            else:
                best_params = optim_results[0].parameters
                train_pf = optim_results[0].profit_factor

            # 2. Test best parameters on test window
            test_strat = strategy_class(parameters=best_params)
            test_backtest = engine.run(test_strat, test_df, symbol=symbol)
            test_metrics = calculate_all_metrics(test_backtest, period_type="out_of_sample")
            m = test_metrics["metrics"]

            test_pf = float(m["profit_factor"])
            test_passed = bool(test_pf > 1.0 and m["final_equity"] > 0)

            windows.append(WalkForwardWindow(
                window_index=window_idx,
                train_start=current_train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                best_params=best_params,
                train_profit_factor=train_pf,
                test_profit_factor=test_pf,
                test_trades=int(m["total_trades"]),
                test_return_pct=float(m["total_return_pct"]),
                test_max_drawdown_pct=float(m["max_drawdown_pct"]),
                passed=test_passed
            ))

            # Step forward
            current_train_start += relativedelta(months=self.step_months)
            window_idx += 1

        logger.info(f"Walk-Forward completed {len(windows)} windows.")
        return windows
