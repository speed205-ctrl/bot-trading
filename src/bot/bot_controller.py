"""Autonomous Bot Controller: thread-safe background execution daemon with telemetry and panic controls."""
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional

from src.bot.execution_engine import ExecutionEngine
from src.bot.notifier import Notifier
from src.bot.risk_guard import RiskGuard
from src.bot.state_manager import StateManager
from src.live.testnet_connector import TestnetConnector
from src.strategies import STRATEGY_REGISTRY, get_strategy
from src.utils.logger import setup_logger

logger = setup_logger("BotController")


class BotController:
    """Orchestrates live bot execution, state reconciliation, and real-time management."""

    def __init__(
        self,
        strategy_id: str = "supertrend",
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        risk_profile: str = "moderate",
        dry_run: bool = True,
        poll_interval: int = 30,
        state_manager: Optional[StateManager] = None,
        connector: Optional[TestnetConnector] = None
    ):
        self.strategy_id = strategy_id
        self.strategy = get_strategy(strategy_id)
        self.symbol = symbol
        self.timeframe = timeframe
        self.dry_run = dry_run
        self.poll_interval = poll_interval

        self.state_manager = state_manager or StateManager()
        self.connector = connector or TestnetConnector()
        self.risk_guard = RiskGuard(risk_profile=risk_profile, state_manager=self.state_manager)
        self.execution_engine = ExecutionEngine(connector=self.connector, state_manager=self.state_manager)
        self.notifier = Notifier()

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_active = False
        self._last_heartbeat = None
        self._last_evaluated_candle = None

    @property
    def is_running(self) -> bool:
        return self._is_active and self._thread is not None and self._thread.is_alive()

    def start(self):
        """Starts the autonomous trading loop in a background daemon thread."""
        if self.is_running:
            logger.warning("El bot ya se encuentra en ejecución.")
            return

        self._stop_event.clear()
        self._is_active = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BotWorkerThread")
        self._thread.start()
        logger.info(f"🤖 Bot iniciado exitosamente para {self.strategy.name} en {self.symbol} [{self.timeframe}] (Modo: {'DRY RUN' if self.dry_run else 'TESTNET EN VIVO'})")

    def stop(self):
        """Stops the autonomous trading loop."""
        if not self.is_running:
            logger.info("El bot ya está detenido.")
            return

        logger.info("Deteniendo el bot de trading...")
        self._stop_event.set()
        self._is_active = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("⏹ Bot de trading detenido de forma segura.")

    def emergency_panic_close(self) -> List[Dict[str, Any]]:
        """Trigger emergency panic button: locks bot and closes all open positions immediately."""
        self.risk_guard.trigger_kill_switch(reason="Cierre de Emergencia activado por el usuario (Panic Button).")
        closed = self.execution_engine.panic_close_all(dry_run=self.dry_run)
        for t in closed:
            self.notifier.notify_position_closed(t)
        return closed

    def _run_loop(self):
        """Core background execution loop."""
        logger.info("Iniciando bucle de control autónomo en segundo plano...")

        while not self._stop_event.is_set():
            try:
                self._execute_cycle()
            except Exception as e:
                logger.error(f"Error inesperado en ciclo del bot: {e}")

            # Sleep in 1-second chunks for fast responsive stop
            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

        self._is_active = False
        logger.info("Bucle de control autónomo finalizado.")

    def _execute_cycle(self):
        """Performs a single evaluation cycle: candle check, position management, and order signals."""
        now_dt = datetime.now(timezone.utc)
        self._last_heartbeat = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        # 1. Fetch recent candles from Binance
        df = self.connector.fetch_recent_data(symbol=self.symbol, timeframe=self.timeframe, limit=250)
        prepared = self.strategy.prepare_data(df)
        latest_bar = prepared.iloc[-1]
        candle_time = str(latest_bar.name)
        current_price = float(latest_bar["close"])
        atr_val = float(latest_bar["atr"]) if "atr" in latest_bar else 0.0

        # 2. Check and manage open position for this symbol
        active_pos = self.state_manager.get_active_position(self.symbol)
        if active_pos:
            entry_p = active_pos["entry_price"]
            sl_p = active_pos["stop_loss"]
            tp_p = active_pos["take_profit"]

            # Update highest price and trailing stop if applicable
            self.state_manager.update_position_extremes(self.symbol, current_price)

            pnl_pct = ((current_price - entry_p) / entry_p) * 100.0

            # Check Stop Loss hit
            if current_price <= sl_p:
                closed = self.execution_engine.close_position(
                    self.symbol,
                    exit_reason="STOP_LOSS_TRIGGERED",
                    current_price=current_price,
                    dry_run=self.dry_run
                )
                if closed:
                    self.notifier.notify_position_closed(closed)
                return

            # Check Take Profit hit
            if current_price >= tp_p:
                closed = self.execution_engine.close_position(
                    self.symbol,
                    exit_reason="TAKE_PROFIT_TRIGGERED",
                    current_price=current_price,
                    dry_run=self.dry_run
                )
                if closed:
                    self.notifier.notify_position_closed(closed)
                return

            # Check Strategy Exit Signal
            if int(latest_bar.get("exit_signal", 0)) == 1:
                closed = self.execution_engine.close_position(
                    self.symbol,
                    exit_reason="STRATEGY_EXIT_SIGNAL",
                    current_price=current_price,
                    dry_run=self.dry_run
                )
                if closed:
                    self.notifier.notify_position_closed(closed)
                return

            logger.info(f"📊 [Posición Abierta] {self.symbol} | Entrada: ${entry_p:,.2f} | Actual: ${current_price:,.2f} | PnL: {pnl_pct:+.2f}% | SL: ${sl_p:,.2f} | TP: ${tp_p:,.2f}")

        else:
            # 3. No open position: check entry signal
            entry_signal = int(latest_bar.get("entry_signal", 0))

            # Avoid re-triggering multiple times on same bar
            if entry_signal == 1 and candle_time != self._last_evaluated_candle:
                sl_calc = self.strategy.get_stop_loss(current_price, atr_val, latest_bar)
                tp_calc = self.strategy.get_take_profit(current_price, atr_val, latest_bar)

                # Validate with Risk Guard
                allowed, reason, size = self.risk_guard.validate_new_order(
                    symbol=self.symbol,
                    entry_price=current_price,
                    stop_loss_price=sl_calc
                )

                if allowed:
                    logger.info(f"🚀 Señal confirmada: Abriendo LONG en {self.symbol} (Size: {size:.4f})")
                    pos = self.execution_engine.open_long_position(
                        symbol=self.symbol,
                        strategy_id=self.strategy_id,
                        size=size,
                        current_price=current_price,
                        stop_loss=sl_calc,
                        take_profit=tp_calc,
                        dry_run=self.dry_run
                    )
                    self._last_evaluated_candle = candle_time
                    self.notifier.notify_position_opened(pos)
                else:
                    logger.warning(f"Señal descartada por gestión de riesgo: {reason}")
                    if "CIRCUIT BREAKER" in reason:
                        self.notifier.notify_circuit_breaker(reason)
            else:
                logger.info(f"[HEARTBEAT {self._last_heartbeat}] {self.symbol}: ${current_price:,.2f} | Sin posición activa | Escaneando...")

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns full live telemetry snapshot for Dashboard display."""
        active_pos = self.state_manager.get_active_position(self.symbol)
        unrealized_pnl = 0.0
        unrealized_pct = 0.0
        current_price = 0.0

        if active_pos:
            try:
                ticker = self.connector.exchange.fetch_ticker(self.symbol)
                current_price = float(ticker["last"])
                entry_p = active_pos["entry_price"]
                amount = active_pos["amount"]
                unrealized_pnl = (current_price - entry_p) * amount
                unrealized_pct = ((current_price - entry_p) / entry_p) * 100.0
            except Exception:
                pass

        daily_stats = self.state_manager.get_daily_pnl()
        recent_trades = self.state_manager.get_trade_history(limit=15)
        circuit_breaker_tripped, cb_reason = self.risk_guard.check_daily_circuit_breaker()

        return {
            "is_running": self.is_running,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy.name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "dry_run": self.dry_run,
            "last_heartbeat": self._last_heartbeat,
            "current_price": current_price,
            "circuit_breaker": {
                "tripped": circuit_breaker_tripped,
                "reason": cb_reason,
                "is_locked": self.risk_guard.is_locked
            },
            "active_position": {
                **active_pos,
                "current_price": current_price,
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pct": round(unrealized_pct, 2)
            } if active_pos else None,
            "daily_performance": daily_stats,
            "recent_trades": recent_trades
        }
