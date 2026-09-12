"""Execution Engine for order placement, precision normalization, and bracket management."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import ccxt

from src.bot.state_manager import StateManager
from src.live.testnet_connector import TestnetConnector
from src.utils.logger import setup_logger

logger = setup_logger("ExecutionEngine")


class ExecutionEngine:
    """Executes trades on Binance (Testnet Sandbox or Live) with precision formatting and order management."""

    def __init__(
        self,
        connector: Optional[TestnetConnector] = None,
        state_manager: Optional[StateManager] = None,
        commission_rate: float = 0.0004,
        slippage_pct: float = 0.0005
    ):
        self.connector = connector or TestnetConnector()
        self.state_manager = state_manager or StateManager()
        self.commission_rate = commission_rate
        self.slippage_pct = slippage_pct

    def get_market_precision(self, symbol: str) -> Dict[str, Any]:
        """Loads market filters (lot size, tick size, min notional)."""
        market = self.connector.exchange.market(symbol) if symbol in self.connector.exchange.markets else None
        if not market:
            return {"amount_precision": 4, "price_precision": 2, "min_amount": 0.001, "min_cost": 5.0}

        precision = market.get("precision", {})
        limits = market.get("limits", {})
        return {
            "amount_precision": precision.get("amount", 4),
            "price_precision": precision.get("price", 2),
            "min_amount": limits.get("amount", {}).get("min", 0.001),
            "min_cost": limits.get("cost", {}).get("min", 5.0)
        }

    def normalize_amount(self, symbol: str, amount: float) -> float:
        """Rounds amount to exchange stepSize precision."""
        try:
            return float(self.connector.exchange.amount_to_precision(symbol, amount))
        except Exception:
            return round(amount, 4)

    def normalize_price(self, symbol: str, price: float) -> float:
        """Rounds price to exchange tickSize precision."""
        try:
            return float(self.connector.exchange.price_to_precision(symbol, price))
        except Exception:
            return round(price, 2)

    def open_long_position(
        self,
        symbol: str,
        strategy_id: str,
        size: float,
        current_price: float,
        stop_loss: float,
        take_profit: float,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Executes a Long entry and tracks the position."""
        normalized_size = self.normalize_amount(symbol, size)
        fill_price = current_price * (1.0 + self.slippage_pct)
        fill_price = self.normalize_price(symbol, fill_price)

        order_id = f"sim_{int(datetime.now(timezone.utc).timestamp()*1000)}"
        if not dry_run and self.connector.has_credentials:
            try:
                order = self.connector.place_testnet_order(
                    symbol=symbol,
                    side="buy",
                    amount=normalized_size,
                    order_type="market"
                )
                order_id = str(order.get("id", order_id))
                fill_price = float(order.get("price") or fill_price)
                logger.info(f"[BINANCE TESTNET] Orden de compra ejecutada: ID {order_id} a ${fill_price:,.2f}")
            except Exception as e:
                logger.error(f"Error al enviar orden a Binance: {e}")
                raise

        # Save to SQLite state manager
        position_record = {
            "symbol": symbol,
            "strategy_id": strategy_id,
            "side": "LONG",
            "entry_price": fill_price,
            "amount": normalized_size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "highest_price": fill_price,
            "lowest_price": fill_price,
            "entry_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "order_id": order_id,
            "extra_data": {"mode": "DRY_RUN" if dry_run else "LIVE_TESTNET"}
        }
        self.state_manager.save_active_position(position_record)
        return position_record

    def close_position(
        self,
        symbol: str,
        exit_reason: str,
        current_price: Optional[float] = None,
        dry_run: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Closes an open position at current market price and registers PnL."""
        pos = self.state_manager.get_active_position(symbol)
        if not pos:
            logger.warning(f"No active position to close for {symbol}")
            return None

        if current_price is None:
            ticker = self.connector.exchange.fetch_ticker(symbol)
            current_price = float(ticker["last"])

        fill_price = current_price * (1.0 - self.slippage_pct)
        fill_price = self.normalize_price(symbol, fill_price)
        amount = pos["amount"]

        if not dry_run and self.connector.has_credentials:
            try:
                self.connector.place_testnet_order(
                    symbol=symbol,
                    side="sell",
                    amount=amount,
                    order_type="market"
                )
                logger.info(f"[BINANCE TESTNET] Posición cerrada para {symbol}")
            except Exception as e:
                logger.error(f"Error al cerrar posición en Binance: {e}")

        # PnL calculations
        entry_val = pos["entry_price"] * amount
        exit_val = fill_price * amount
        gross_pnl = exit_val - entry_val
        commissions = (entry_val + exit_val) * self.commission_rate
        net_pnl = gross_pnl - commissions
        return_pct = (net_pnl / entry_val) * 100.0 if entry_val > 0 else 0.0

        trade_record = {
            "symbol": symbol,
            "strategy_id": pos["strategy_id"],
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": fill_price,
            "amount": amount,
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "return_pct": round(return_pct, 2),
            "entry_time": pos["entry_time"],
            "exit_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "exit_reason": exit_reason
        }

        self.state_manager.record_closed_trade(trade_record)
        return trade_record

    def panic_close_all(self, dry_run: bool = True) -> List[Dict[str, Any]]:
        """Emergency Panic Button: closes ALL active positions immediately."""
        logger.warning("🚨 [PANIC BUTTON DISPARADO] Cerrando todas las posiciones abiertas...")
        open_positions = self.state_manager.get_all_active_positions()
        closed_trades = []

        for p in open_positions:
            try:
                closed = self.close_position(
                    symbol=p["symbol"],
                    exit_reason="EMERGENCY_PANIC_CLOSE",
                    dry_run=dry_run
                )
                if closed:
                    closed_trades.append(closed)
            except Exception as e:
                logger.error(f"Error en panic close de {p['symbol']}: {e}")

        return closed_trades
