"""Trading strategy implementations and registry."""
from typing import Dict, Type

from src.strategies.base_strategy import BaseStrategy
from src.strategies.bollinger_breakout import BollingerBreakoutStrategy
from src.strategies.ema_cross_adx import EmaCrossADXStrategy
from src.strategies.macd_momentum import MacdMomentumStrategy
from src.strategies.rsi_mean_reversion import RsiMeanReversionStrategy
from src.strategies.trend_pullback_atr import TrendPullbackATRStrategy

STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    "trend_pullback_atr": TrendPullbackATRStrategy,
    "ema_cross_adx": EmaCrossADXStrategy,
    "bollinger_breakout": BollingerBreakoutStrategy,
    "rsi_mean_reversion": RsiMeanReversionStrategy,
    "macd_momentum": MacdMomentumStrategy,
}


def get_strategy(strategy_id: str, **kwargs) -> BaseStrategy:
    """Instantiates a strategy by ID with optional parameters."""
    strat_cls = STRATEGY_REGISTRY.get(strategy_id.lower())
    if not strat_cls:
        available = list(STRATEGY_REGISTRY.keys())
        raise KeyError(f"Unknown strategy ID: '{strategy_id}'. Available: {available}")
    return strat_cls(**kwargs)
