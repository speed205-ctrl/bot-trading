"""Unit tests for Backtest Engine, CostCalculator, PositionManager, and OrderSimulator."""
import numpy as np
import pandas as pd
import pytest

from src.backtest.cost_calculator import CostCalculator, CostConfig
from src.backtest.engine import BacktestEngine
from src.backtest.order_simulator import OrderSimulator
from src.backtest.position_manager import PRESET_PROFILES, PositionManager
from src.strategies.trend_pullback_atr import TrendPullbackATRStrategy


@pytest.fixture
def synthetic_candles():
    """Generates synthetic trending candles with known swings."""
    np.random.seed(123)
    n = 200
    dates = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    # Upward trend with pullbacks
    trend = np.linspace(20000, 25000, n)
    noise = np.sin(np.linspace(0, 10 * np.pi, n)) * 300
    close = trend + noise
    high = close + np.random.uniform(50, 150, n)
    low = close - np.random.uniform(50, 150, n)
    open_p = (high + low) / 2.0
    volume = np.random.uniform(500, 2000, n)

    df = pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    return df


def test_cost_calculator():
    """Verifies slippage and commission calculations."""
    calc = CostCalculator(CostConfig(commission_rate=0.0004, slippage_pct=0.0005))
    price = 10000.0

    buy_price = calc.apply_entry_slippage(price, "long")
    sell_price = calc.apply_exit_slippage(price, "long")

    assert buy_price == 10000.0 * 1.0005
    assert sell_price == 10000.0 * 0.9995

    comm = calc.calculate_commission(10000.0)
    assert comm == 4.0


def test_position_manager_sizing():
    """Verifies position sizing respects risk % and ATR distance."""
    pm = PositionManager(PRESET_PROFILES["moderate"])  # 2% risk
    capital = 10000.0
    entry_p = 50000.0
    sl_p = 48000.0  # distance = 2000

    # Risk amount = 10000 * 0.02 = 200. Size = 200 / 2000 = 0.1 BTC
    size = pm.calculate_position_size(capital, entry_p, sl_p)
    assert pytest.approx(size, rel=1e-3) == 0.1

    # Check leverage cap: max leverage = 10x, max notional = 100,000
    sl_p_tiny = 49999.0  # distance = 1, uncapped size would be 200 BTC = 10,000,000 notional
    capped_size = pm.calculate_position_size(capital, entry_p, sl_p_tiny)
    assert pytest.approx(capped_size * entry_p, rel=1e-3) == 100000.0


def test_order_simulator_stop_loss():
    """Verifies stop-loss triggers when candle low breaches stop price."""
    sim = OrderSimulator()
    pos, comm = sim.execute_entry(
        symbol="BTC/USDT",
        direction="long",
        open_price=20000.0,
        size=1.0,
        timestamp=pd.Timestamp("2023-01-01 00:00:00", tz="UTC"),
        stop_loss=19500.0,
        take_profit=21500.0,
        leverage=5,
        risk_profile_name="moderate"
    )
    assert pos.size == 1.0

    candle_no_hit = pd.Series({"open": 20000, "high": 20200, "low": 19600, "close": 20100})
    trade_no_hit = sim.check_position_exit(pos, candle_no_hit, pd.Timestamp("2023-01-01 01:00:00", tz="UTC"))
    assert trade_no_hit is None

    candle_hit = pd.Series({"open": 19600, "high": 19700, "low": 19400, "close": 19450})
    trade_hit = sim.check_position_exit(pos, candle_hit, pd.Timestamp("2023-01-01 02:00:00", tz="UTC"))
    assert trade_hit is not None
    assert trade_hit.exit_reason == "stop_loss"
    assert trade_hit.exit_price < 19500.0  # due to slippage


def test_backtest_engine_run(synthetic_candles):
    """Verifies full execution of BacktestEngine with TrendPullbackATR."""
    strategy = TrendPullbackATRStrategy()
    engine = BacktestEngine(initial_capital=10000.0, risk_profile="conservative")

    result = engine.run(strategy, synthetic_candles, symbol="BTC/USDT")

    assert result.strategy_name == "Trend Pullback ATR"
    assert result.initial_capital == 10000.0
    assert not result.equity_curve.empty
    assert "equity" in result.equity_curve.columns
    assert "drawdown_pct" in result.equity_curve.columns
    assert result.equity_curve["drawdown_pct"].min() >= 0.0
