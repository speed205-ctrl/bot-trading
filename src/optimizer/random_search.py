"""Random search parameter optimizer."""
import random
from typing import Any, Dict, List, Optional
import pandas as pd

from src.optimizer.grid_search import GridSearchOptimizer, OptimizationResult
from src.utils.logger import setup_logger

logger = setup_logger("RandomSearch")


class RandomSearchOptimizer(GridSearchOptimizer):
    """Samples random parameter combinations from the search space."""

    def __init__(
        self,
        target_metric: str = "profit_factor",
        max_combinations: int = 50,
        min_trades: int = 30,
        initial_capital: float = 10000.0,
        risk_profile: str = "moderate",
        random_state: int = 42
    ):
        super().__init__(
            target_metric=target_metric,
            max_combinations=max_combinations,
            min_trades=min_trades,
            initial_capital=initial_capital,
            risk_profile=risk_profile
        )
        self.random_state = random_state

    def _generate_param_combinations(self, param_ranges: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Randomly samples parameter combinations."""
        random.seed(self.random_state)
        keys = list(param_ranges.keys())
        combos = []
        seen = set()

        max_attempts = self.max_combinations * 10
        attempts = 0

        while len(combos) < self.max_combinations and attempts < max_attempts:
            attempts += 1
            choice = {k: random.choice(param_ranges[k]) for k in keys}
            frozen = tuple(sorted(choice.items()))
            if frozen not in seen:
                seen.add(frozen)
                combos.append(choice)

        return combos
