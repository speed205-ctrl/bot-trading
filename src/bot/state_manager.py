"""SQLite state manager for bot positions, trades, and circuit breaker metrics."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from src.utils.logger import setup_logger

logger = setup_logger("StateManager")


class StateManager:
    """Manages persistent SQLite state for real-time bot operations."""

    def __init__(self, db_path: str = "data/bot_state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_positions (
                    symbol TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    amount REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    highest_price REAL NOT NULL,
                    lowest_price REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    order_id TEXT,
                    extra_data TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    amount REAL NOT NULL,
                    gross_pnl REAL NOT NULL,
                    net_pnl REAL NOT NULL,
                    return_pct REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    exit_reason TEXT NOT NULL,
                    date_str TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_active_position(self, pos: Dict[str, Any]):
        """Persists or updates an active open position."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO active_positions 
                (symbol, strategy_id, side, entry_price, amount, stop_loss, take_profit, highest_price, lowest_price, entry_time, order_id, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pos["symbol"],
                pos["strategy_id"],
                pos["side"],
                float(pos["entry_price"]),
                float(pos["amount"]),
                float(pos["stop_loss"]),
                float(pos["take_profit"]),
                float(pos.get("highest_price", pos["entry_price"])),
                float(pos.get("lowest_price", pos["entry_price"])),
                str(pos["entry_time"]),
                str(pos.get("order_id", "")),
                json.dumps(pos.get("extra_data", {}))
            ))
            conn.commit()
            logger.info(f"Active position saved for {pos['symbol']} at ${pos['entry_price']:,.2f}")

    def get_active_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieves active position for a symbol, if any."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM active_positions WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["extra_data"] = json.loads(data["extra_data"]) if data.get("extra_data") else {}
            return data

    def get_all_active_positions(self) -> List[Dict[str, Any]]:
        """Retrieves all currently open positions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM active_positions")
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["extra_data"] = json.loads(item["extra_data"]) if item.get("extra_data") else {}
                results.append(item)
            return results

    def update_position_extremes(self, symbol: str, current_price: float, new_sl: Optional[float] = None):
        """Updates highest/lowest prices and trailing stop loss for an open position."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            pos = self.get_active_position(symbol)
            if not pos:
                return

            highest = max(pos["highest_price"], current_price)
            lowest = min(pos["lowest_price"], current_price)
            sl = new_sl if new_sl is not None else pos["stop_loss"]

            cursor.execute("""
                UPDATE active_positions 
                SET highest_price = ?, lowest_price = ?, stop_loss = ?
                WHERE symbol = ?
            """, (highest, lowest, sl, symbol))
            conn.commit()

    def remove_active_position(self, symbol: str):
        """Removes a position when it is closed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_positions WHERE symbol = ?", (symbol,))
            conn.commit()
            logger.info(f"Active position removed for {symbol}")

    def record_closed_trade(self, trade: Dict[str, Any]):
        """Records a closed trade in historical trades table."""
        now_dt = datetime.now(timezone.utc)
        date_str = trade.get("date_str") or now_dt.strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades_history 
                (symbol, strategy_id, side, entry_price, exit_price, amount, gross_pnl, net_pnl, return_pct, entry_time, exit_time, exit_reason, date_str)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade["symbol"],
                trade["strategy_id"],
                trade["side"],
                float(trade["entry_price"]),
                float(trade["exit_price"]),
                float(trade["amount"]),
                float(trade.get("gross_pnl", 0.0)),
                float(trade["net_pnl"]),
                float(trade["return_pct"]),
                str(trade["entry_time"]),
                str(trade["exit_time"]),
                str(trade["exit_reason"]),
                date_str
            ))
            conn.commit()
            self.remove_active_position(trade["symbol"])
            logger.info(f"Recorded closed trade for {trade['symbol']}: Net PnL ${trade['net_pnl']:+,.2f} ({trade['return_pct']:+.2f}%)")

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches recent closed trades."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades_history ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_daily_pnl(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Calculates today's realized PnL and trade statistics for circuit breaker checks."""
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT net_pnl, return_pct 
                FROM trades_history 
                WHERE date_str = ?
            """, (date_str,))
            rows = cursor.fetchall()

            total_net_pnl = sum(r["net_pnl"] for r in rows)
            wins = sum(1 for r in rows if r["net_pnl"] > 0)
            losses = sum(1 for r in rows if r["net_pnl"] < 0)

            return {
                "date": date_str,
                "total_trades": len(rows),
                "total_net_pnl": round(total_net_pnl, 2),
                "wins": wins,
                "losses": losses,
                "win_rate": round((wins / len(rows) * 100.0) if rows else 0.0, 1)
            }
