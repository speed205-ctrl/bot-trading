"""Unit tests for Phase 2 Autonomous Bot components."""
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from src.bot.state_manager import StateManager
from src.bot.risk_guard import RiskGuard
from src.bot.execution_engine import ExecutionEngine
from src.bot.bot_controller import BotController


@pytest.fixture
def temp_state_manager(tmp_path):
    """Provides a fresh StateManager with isolated SQLite DB."""
    db_file = tmp_path / "test_bot_state.db"
    return StateManager(db_path=str(db_file))


def test_state_manager_positions_and_trades(temp_state_manager):
    """Verifies storing, updating, retrieving, and closing positions in SQLite."""
    sm = temp_state_manager

    # 1. Save active position
    pos_data = {
        "symbol": "BTC/USDT",
        "strategy_id": "supertrend",
        "side": "LONG",
        "entry_price": 50000.0,
        "amount": 0.1,
        "stop_loss": 48000.0,
        "take_profit": 54000.0,
        "highest_price": 50000.0,
        "lowest_price": 50000.0,
        "entry_time": "2024-01-01 12:00:00 UTC",
        "order_id": "sim_123"
    }
    sm.save_active_position(pos_data)

    pos = sm.get_active_position("BTC/USDT")
    assert pos is not None
    assert pos["symbol"] == "BTC/USDT"
    assert pos["entry_price"] == 50000.0
    assert pos["amount"] == 0.1

    # 2. Update extremes
    sm.update_position_extremes("BTC/USDT", current_price=52000.0, new_sl=49000.0)
    updated_pos = sm.get_active_position("BTC/USDT")
    assert updated_pos["highest_price"] == 52000.0
    assert updated_pos["stop_loss"] == 49000.0

    # 3. Record closed trade
    trade_data = {
        "symbol": "BTC/USDT",
        "strategy_id": "supertrend",
        "side": "LONG",
        "entry_price": 50000.0,
        "exit_price": 53000.0,
        "amount": 0.1,
        "gross_pnl": 300.0,
        "net_pnl": 290.0,
        "return_pct": 5.8,
        "entry_time": "2024-01-01 12:00:00 UTC",
        "exit_time": "2024-01-01 16:00:00 UTC",
        "exit_reason": "TAKE_PROFIT_TRIGGERED",
        "date_str": "2024-01-01"
    }
    sm.record_closed_trade(trade_data)

    # Position should no longer be active
    assert sm.get_active_position("BTC/USDT") is None

    # History should contain trade
    history = sm.get_trade_history()
    assert len(history) == 1
    assert history[0]["net_pnl"] == 290.0

    # Daily stats
    daily = sm.get_daily_pnl("2024-01-01")
    assert daily["total_trades"] == 1
    assert daily["total_net_pnl"] == 290.0
    assert daily["wins"] == 1


def test_risk_guard_circuit_breaker(temp_state_manager):
    """Verifies that daily drawdown limit triggers circuit breaker."""
    sm = temp_state_manager
    rg = RiskGuard(risk_profile="moderate", state_manager=sm, base_capital=10000.0)

    # Moderate max daily drawdown is 5% ($500)
    # Record a losing trade of $600 today
    today_str = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    loss_trade = {
        "symbol": "BTC/USDT",
        "strategy_id": "supertrend",
        "side": "LONG",
        "entry_price": 50000.0,
        "exit_price": 44000.0,
        "amount": 0.1,
        "gross_pnl": -600.0,
        "net_pnl": -610.0,
        "return_pct": -12.0,
        "entry_time": "2024-01-01 12:00:00 UTC",
        "exit_time": "2024-01-01 14:00:00 UTC",
        "exit_reason": "STOP_LOSS",
        "date_str": today_str
    }
    sm.record_closed_trade(loss_trade)

    tripped, reason = rg.check_daily_circuit_breaker(current_capital=10000.0)
    assert tripped is True
    assert "CIRCUIT BREAKER DISPARADO" in reason

    # Attempting to validate a new order should be rejected
    allowed, val_reason, size = rg.validate_new_order("ETH/USDT", 3000.0, 2900.0)
    assert allowed is False
    assert "CIRCUIT BREAKER" in val_reason


def test_execution_engine_simulated_flow(temp_state_manager):
    """Verifies order opening, closing, and panic close on ExecutionEngine."""
    sm = temp_state_manager
    mock_connector = MagicMock()
    mock_connector.has_credentials = False
    mock_connector.exchange.market.return_value = {"precision": {"amount": 4, "price": 2}, "limits": {"cost": {"min": 5.0}}}
    mock_connector.exchange.amount_to_precision.side_effect = lambda s, a: str(a)
    mock_connector.exchange.price_to_precision.side_effect = lambda s, p: str(round(p, 2))

    engine = ExecutionEngine(connector=mock_connector, state_manager=sm)

    # 1. Open long
    pos = engine.open_long_position(
        symbol="BTC/USDT",
        strategy_id="supertrend",
        size=0.05,
        current_price=50000.0,
        stop_loss=48000.0,
        take_profit=54000.0,
        dry_run=True
    )
    assert pos["symbol"] == "BTC/USDT"
    assert sm.get_active_position("BTC/USDT") is not None

    # 2. Close position
    trade = engine.close_position("BTC/USDT", exit_reason="MANUAL_TEST", current_price=52000.0, dry_run=True)
    assert trade is not None
    assert trade["exit_reason"] == "MANUAL_TEST"
    assert trade["net_pnl"] > 0
    assert sm.get_active_position("BTC/USDT") is None

    # 3. Panic close all
    engine.open_long_position(
        symbol="ETH/USDT",
        strategy_id="donchian_breakout",
        size=1.0,
        current_price=3000.0,
        stop_loss=2800.0,
        take_profit=3400.0,
        dry_run=True
    )
    assert sm.get_active_position("ETH/USDT") is not None

    closed_all = engine.panic_close_all(dry_run=True)
    assert len(closed_all) == 1
    assert closed_all[0]["symbol"] == "ETH/USDT"
    assert sm.get_active_position("ETH/USDT") is None


def test_bot_controller_lifecycle(temp_state_manager):
    """Verifies starting, telemetry query, emergency panic, and stopping of BotController."""
    sm = temp_state_manager
    mock_connector = MagicMock()
    mock_connector.has_credentials = False
    mock_connector.exchange.market.return_value = {"precision": {"amount": 4, "price": 2}, "limits": {"cost": {"min": 5.0}}}
    mock_connector.exchange.amount_to_precision.side_effect = lambda s, a: str(a)
    mock_connector.exchange.price_to_precision.side_effect = lambda s, p: str(round(p, 2))
    mock_connector.exchange.fetch_ticker.return_value = {"last": 65000.0}

    # Synthetic candles dataframe
    dates = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    prices = 60000.0 + np.cumsum(np.random.normal(0, 100, 100))
    mock_df = pd.DataFrame({
        "open": prices,
        "high": prices + 50.0,
        "low": prices - 50.0,
        "close": prices + 10.0,
        "volume": 1000.0
    }, index=dates)
    mock_connector.fetch_recent_data.return_value = mock_df

    controller = BotController(
        strategy_id="supertrend",
        symbol="BTC/USDT",
        timeframe="1h",
        risk_profile="moderate",
        dry_run=True,
        poll_interval=1,
        state_manager=sm,
        connector=mock_connector
    )

    # 1. Telemetry before start
    tel = controller.get_telemetry()
    assert tel["is_running"] is False
    assert tel["strategy_id"] == "supertrend"
    assert tel["active_position"] is None

    # 2. Start
    controller.start()
    assert controller.is_running is True

    # 3. Telemetry while running
    tel_running = controller.get_telemetry()
    assert tel_running["is_running"] is True

    # 4. Emergency panic close
    sm.save_active_position({
        "symbol": "BTC/USDT",
        "strategy_id": "supertrend",
        "side": "LONG",
        "entry_price": 64000.0,
        "amount": 0.05,
        "stop_loss": 62000.0,
        "take_profit": 68000.0,
        "highest_price": 64000.0,
        "lowest_price": 64000.0,
        "entry_time": "2024-01-01 12:00:00 UTC"
    })
    panic_res = controller.emergency_panic_close()
    assert len(panic_res) == 1
    assert panic_res[0]["symbol"] == "BTC/USDT"
    assert sm.get_active_position("BTC/USDT") is None
    assert controller.risk_guard.is_locked is True

    # 5. Stop
    controller.stop()
    assert controller.is_running is False

