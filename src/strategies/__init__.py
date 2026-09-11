"""Trading strategy implementations and registry."""
from typing import Dict, Type

from src.strategies.base_strategy import BaseStrategy
from src.strategies.bollinger_breakout import BollingerBreakoutStrategy
from src.strategies.donchian_breakout import DonchianBreakoutStrategy
from src.strategies.ema_cross_adx import EmaCrossADXStrategy
from src.strategies.keltner_squeeze import KeltnerSqueezeStrategy
from src.strategies.macd_momentum import MacdMomentumStrategy
from src.strategies.rsi_mean_reversion import RsiMeanReversionStrategy
from src.strategies.stoch_rsi import StochRsiMeanReversionStrategy
from src.strategies.supertrend import SupertrendStrategy
from src.strategies.trend_pullback_atr import TrendPullbackATRStrategy
from src.strategies.triple_ema_ribbon import TripleEmaRibbonStrategy
from src.strategies.vwap_reversion import VwapMeanReversionStrategy

STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    # Original 5 strategies from spec
    "trend_pullback_atr": TrendPullbackATRStrategy,
    "ema_cross_adx": EmaCrossADXStrategy,
    "bollinger_breakout": BollingerBreakoutStrategy,
    "rsi_mean_reversion": RsiMeanReversionStrategy,
    "macd_momentum": MacdMomentumStrategy,
    # 6 New Advanced Quant strategies
    "supertrend": SupertrendStrategy,
    "donchian_breakout": DonchianBreakoutStrategy,
    "keltner_squeeze": KeltnerSqueezeStrategy,
    "stoch_rsi": StochRsiMeanReversionStrategy,
    "vwap_reversion": VwapMeanReversionStrategy,
    "triple_ema_ribbon": TripleEmaRibbonStrategy,
}


def get_strategy(strategy_id: str, **kwargs) -> BaseStrategy:
    """Instantiates a strategy by ID with optional parameters."""
    strat_cls = STRATEGY_REGISTRY.get(strategy_id.lower())
    if not strat_cls:
        available = list(STRATEGY_REGISTRY.keys())
        raise KeyError(f"Unknown strategy ID: '{strategy_id}'. Available: {available}")
    return strat_cls(**kwargs)
