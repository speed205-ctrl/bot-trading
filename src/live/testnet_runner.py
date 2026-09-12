"""Binance Testnet Runner for real-time signal evaluation and simulated or testnet order execution."""
from typing import Any, Dict, Optional
import pandas as pd

from src.backtest.position_manager import PRESET_PROFILES, PositionManager
from src.live.testnet_connector import TestnetConnector
from src.strategies import STRATEGY_REGISTRY, get_strategy
from src.utils.logger import setup_logger

logger = setup_logger("TestnetRunner")


class TestnetRunner:
    """Evaluates strategy signals on current Binance Testnet market data and handles order execution."""
    __test__ = False

    def __init__(
        self,
        strategy_id: str = "supertrend",
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        risk_profile: str = "moderate",
        dry_run: bool = True,
        connector: Optional[TestnetConnector] = None
    ):
        self.strategy_id = strategy_id
        self.strategy = get_strategy(strategy_id)
        self.symbol = symbol
        self.timeframe = timeframe
        self.profile = PRESET_PROFILES.get(risk_profile.lower(), PRESET_PROFILES["moderate"])
        self.dry_run = dry_run
        self.connector = connector or TestnetConnector()
        self.position_manager = PositionManager(self.profile)

    def evaluate_signals(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Fetches latest data (or uses provided df) and checks for active entry/exit signals on the latest bar."""
        logger.info(f"Evaluating signals for '{self.strategy.name}' on {self.symbol} [{self.timeframe}]...")

        if df is None:
            df = self.connector.fetch_recent_data(symbol=self.symbol, timeframe=self.timeframe, limit=250)

        prepared = self.strategy.prepare_data(df)
        latest_bar = prepared.iloc[-1]
        prev_bar = prepared.iloc[-2] if len(prepared) > 1 else latest_bar

        entry_signal = int(latest_bar.get("entry_signal", 0))
        exit_signal = int(latest_bar.get("exit_signal", 0))
        close_price = float(latest_bar["close"])
        atr_val = float(latest_bar["atr"]) if "atr" in latest_bar else 0.0

        sl_price = self.strategy.get_stop_loss(close_price, atr_val, latest_bar)
        tp_price = self.strategy.get_take_profit(close_price, atr_val, latest_bar)

        order_executed = None
        action_taken = "HOLD"

        if entry_signal == 1:
            action_taken = "BUY / LONG"
            # Calculate sizing assuming virtual balance of $10,000 if testnet balance unavailable
            size = self.position_manager.calculate_position_size(
                capital=10000.0,
                entry_price=close_price,
                stop_loss_price=sl_price,
                leverage=self.profile.max_leverage
            )

            if self.dry_run or not self.connector.has_credentials:
                logger.info(f"[DRY RUN] Would execute BUY on {self.symbol}: Size={size:.4f}, Price=${close_price:,.2f}, SL=${sl_price:,.2f}, TP=${tp_price:,.2f}")
                order_executed = {
                    "mode": "DRY_RUN",
                    "side": "buy",
                    "size": size,
                    "price": close_price,
                    "stop_loss": sl_price,
                    "take_profit": tp_price
                }
            else:
                order_executed = self.connector.place_testnet_order(
                    symbol=self.symbol,
                    side="buy",
                    amount=size,
                    order_type="market"
                )

        elif exit_signal == 1:
            action_taken = "SELL / EXIT"
            if self.dry_run or not self.connector.has_credentials:
                logger.info(f"[DRY RUN] Would execute EXIT on {self.symbol} at ${close_price:,.2f}")
                order_executed = {"mode": "DRY_RUN", "side": "sell", "price": close_price}
            else:
                # Close open position
                order_executed = self.connector.place_testnet_order(
                    symbol=self.symbol,
                    side="sell",
                    amount=0.01,
                    order_type="market"
                )

        return {
            "strategy": self.strategy.name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "last_timestamp": str(latest_bar.name),
            "close_price": close_price,
            "action": action_taken,
            "entry_signal": entry_signal,
            "exit_signal": exit_signal,
            "stop_loss": sl_price,
            "take_profit": tp_price,
            "order": order_executed
        }

    def run_loop(self, poll_interval: int = 60, max_iterations: Optional[int] = None):
        """Runs continuous real-time execution loop, monitoring candles and managing orders/positions."""
        import time
        from datetime import datetime

        logger.info(f"Iniciando bucle de ejecución continua en vivo ({self.symbol} - {self.timeframe})...")
        logger.info(f"Modo: {'DRY-RUN (Simulación sin riesgo)' if self.dry_run else 'TESTNET EN VIVO'}")
        logger.info(f"Estrategia: {self.strategy.name} | Intervalo de chequeo: {poll_interval}s")

        active_position: Optional[Dict[str, Any]] = None
        iteration = 0
        last_evaluated_timestamp = None

        try:
            while max_iterations is None or iteration < max_iterations:
                iteration += 1
                now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

                try:
                    res = self.evaluate_signals()
                    close_p = res["close_price"]
                    candle_ts = res["last_timestamp"]

                    # Check position SL / TP triggers if currently in a trade
                    if active_position is not None:
                        entry_p = active_position["entry_price"]
                        sl_p = active_position["sl"]
                        tp_p = active_position["tp"]
                        pnl_pct = ((close_p - entry_p) / entry_p) * 100.0

                        logger.info(f"[POSICION ABIERTA] Entrada: ${entry_p:,.2f} | Actual: ${close_p:,.2f} | PnL: {pnl_pct:+.2f}% | SL: ${sl_p:,.2f} | TP: ${tp_p:,.2f}")

                        if close_p <= sl_p:
                            logger.warning(f"[STOP LOSS ALCANZADO] Cerrando posición a ${close_p:,.2f} (PnL: {pnl_pct:+.2f}%)")
                            active_position = None
                        elif close_p >= tp_p:
                            logger.info(f"[TAKE PROFIT ALCANZADO] Cerrando posición a ${close_p:,.2f} (PnL: {pnl_pct:+.2f}%)")
                            active_position = None
                        elif res["exit_signal"] == 1:
                            logger.info(f"[SEÑAL DE SALIDA] Estrategia indicó cierre a ${close_p:,.2f} (PnL: {pnl_pct:+.2f}%)")
                            active_position = None
                    else:
                        # No active position: check if entry triggered on a new candle
                        if res["entry_signal"] == 1 and candle_ts != last_evaluated_timestamp:
                            logger.info(f"[NUEVA POSICION ABIERTA] Comprando {self.symbol} a ${close_p:,.2f}")
                            active_position = {
                                "entry_price": close_p,
                                "sl": res["stop_loss"],
                                "tp": res["take_profit"],
                                "time": candle_ts
                            }
                            last_evaluated_timestamp = candle_ts
                        else:
                            logger.info(f"[HEARTBEAT {now_str}] {self.symbol}: ${close_p:,.2f} | Señal: {res['action']} | Sin posición activa.")

                except Exception as exc:
                    logger.error(f"Error en iteración de monitoreo: {exc}")

                if max_iterations is not None and iteration >= max_iterations:
                    break

                time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("[DETENIDO] Monitoreo en vivo detenido por el usuario (Ctrl+C).")

