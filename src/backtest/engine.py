"""Backtesting simulation engine."""
from dataclasses import dataclass
from typing import List, Optional, Union
import numpy as np
import pandas as pd

from src.backtest.cost_calculator import CostCalculator, CostConfig
from src.backtest.order_simulator import OrderSimulator, Trade
from src.backtest.position_manager import PRESET_PROFILES, PositionManager, RiskProfile
from src.strategies.base_strategy import BaseStrategy
from src.utils.logger import setup_logger

logger = setup_logger("BacktestEngine")


@dataclass
class BacktestResult:
    strategy_name: str
    risk_profile_name: str
    symbol: str
    timeframe: str
    initial_capital: float
    final_equity: float
    trades: List[Trade]
    equity_curve: pd.DataFrame


class BacktestEngine:
    """Simulates trading strategy execution on historical OHLCV data."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        risk_profile: Union[str, RiskProfile] = "moderate",
        commission_rate: float = 0.0004,
        slippage_pct: float = 0.0005,
    ):
        self.initial_capital = initial_capital
        if isinstance(risk_profile, str):
            self.profile = PRESET_PROFILES.get(risk_profile.lower(), PRESET_PROFILES["moderate"])
        else:
            self.profile = risk_profile

        self.cost_config = CostConfig(commission_rate=commission_rate, slippage_pct=slippage_pct)
        self.cost_calculator = CostCalculator(self.cost_config)
        self.order_simulator = OrderSimulator(self.cost_calculator)

    def run(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        symbol: str = "BTC/USDT"
    ) -> BacktestResult:
        """Executes candle-by-candle backtesting on prepared dataset."""
        logger.info(f"Starting backtest for '{strategy.name}' on {symbol} with capital ${self.initial_capital:,.2f} ({self.profile.name})")

        # Prepare data with indicators and signals
        data = strategy.prepare_data(df)
        if "atr" not in data.columns:
            raise ValueError(f"Strategy '{strategy.name}' did not produce an 'atr' column required for stop sizing.")

        position_manager = PositionManager(self.profile)
        trades: List[Trade] = []
        equity_records = []

        cash = self.initial_capital
        peak_equity = self.initial_capital
        pending_entry_signal = False
        pending_exit_signal = False
        last_atr = 0.0

        for idx, (timestamp, row) in enumerate(data.iterrows()):
            open_p = row["open"]
            high_p = row["high"]
            low_p = row["low"]
            close_p = row["close"]
            atr_val = row["atr"] if not pd.isna(row["atr"]) else last_atr
            last_atr = atr_val

            # 1. Process pending ENTRY order from previous candle signal
            if pending_entry_signal and position_manager.can_open_position(symbol):
                sl_price = strategy.get_stop_loss(open_p, atr_val, row)
                tp_price = strategy.get_take_profit(open_p, atr_val, row)

                size = position_manager.calculate_position_size(
                    capital=cash,
                    entry_price=open_p,
                    stop_loss_price=sl_price,
                    leverage=self.profile.max_leverage
                )

                if size > 0:
                    pos, comm = self.order_simulator.execute_entry(
                        symbol=symbol,
                        direction=strategy.direction.replace("_only", ""),
                        open_price=open_p,
                        size=size,
                        timestamp=timestamp,
                        stop_loss=sl_price,
                        take_profit=tp_price,
                        leverage=self.profile.max_leverage,
                        risk_profile_name=self.profile.name
                    )
                    # Deduct margin and entry commission
                    if cash >= (pos.margin + comm):
                        cash -= (pos.margin + comm)
                        position_manager.open_positions[symbol] = pos
                pending_entry_signal = False

            # 2. Check EXITS on active position for the current candle
            if symbol in position_manager.open_positions:
                pos = position_manager.open_positions[symbol]
                closed_trade = self.order_simulator.check_position_exit(
                    position=pos,
                    candle=row,
                    timestamp=timestamp,
                    signal_exit_active=pending_exit_signal
                )
                if closed_trade is not None:
                    # Return margin and add net PnL (commissions already subtracted in net_pnl)
                    cash += (pos.margin + closed_trade.net_pnl)
                    trades.append(closed_trade)
                    del position_manager.open_positions[symbol]
                pending_exit_signal = False

            # 3. Calculate current bar Equity (Cash + Unrealized PnL of open positions)
            unrealized_pnl = 0.0
            if symbol in position_manager.open_positions:
                pos = position_manager.open_positions[symbol]
                unrealized_pnl = (close_p - pos.entry_price) * pos.size

            current_equity = cash + (pos.margin + unrealized_pnl if symbol in position_manager.open_positions else 0.0)

            # Drawdown calculations
            peak_equity = max(peak_equity, current_equity)
            drawdown_pct = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0

            equity_records.append({
                "datetime": timestamp,
                "equity": current_equity,
                "cash": cash,
                "drawdown_pct": drawdown_pct,
                "peak_equity": peak_equity,
                "open_positions": position_manager.current_open_count
            })

            # Check for capital depletion
            if current_equity <= 0:
                logger.warning(f"Capital depleted at {timestamp}. Terminating backtest.")
                break

            # 4. Read strategy signals for NEXT candle execution
            pending_entry_signal = bool(row.get("entry_signal", 0) == 1)
            pending_exit_signal = bool(row.get("exit_signal", 0) == 1)

        equity_df = pd.DataFrame(equity_records)
        if not equity_df.empty:
            equity_df.set_index("datetime", inplace=True)

        final_equity = equity_df["equity"].iloc[-1] if not equity_df.empty else self.initial_capital
        logger.info(f"Backtest completed. Total trades: {len(trades)}, Final Equity: ${final_equity:,.2f}")

        return BacktestResult(
            strategy_name=strategy.name,
            risk_profile_name=self.profile.name,
            symbol=symbol,
            timeframe=strategy.preferred_timeframe,
            initial_capital=self.initial_capital,
            final_equity=final_equity,
            trades=trades,
            equity_curve=equity_df
        )
