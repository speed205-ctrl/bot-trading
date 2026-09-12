"""Notification dispatcher for bot alerts (Console, Telegram/Discord webhooks)."""
import urllib.request
import json
from typing import Any, Dict, Optional

from src.utils.logger import setup_logger

logger = setup_logger("Notifier")


class Notifier:
    """Dispatches trade alerts and circuit breaker notices."""

    def __init__(self, telegram_bot_token: Optional[str] = None, telegram_chat_id: Optional[str] = None, discord_webhook_url: Optional[str] = None):
        self.telegram_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.discord_webhook = discord_webhook_url

    def _send_discord(self, message: str):
        if not self.discord_webhook:
            return
        try:
            req = urllib.request.Request(
                self.discord_webhook,
                data=json.dumps({"content": message}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.error(f"Error enviando notificación Discord: {e}")

    def _send_telegram(self, message: str):
        if not self.telegram_token or not self.telegram_chat_id:
            return
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = json.dumps({"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.error(f"Error enviando notificación Telegram: {e}")

    def broadcast(self, message: str):
        """Sends message to all configured external endpoints."""
        self._send_telegram(message)
        self._send_discord(message)

    def notify_position_opened(self, pos: Dict[str, Any]):
        msg = (
            f"🚀 *NUEVA POSICIÓN ABIERTA*\n"
            f"• Par: `{pos['symbol']}`\n"
            f"• Estrategia: `{pos['strategy_id']}`\n"
            f"• Lado: `{pos['side']}`\n"
            f"• Entrada: `${pos['entry_price']:,.2f}`\n"
            f"• Cantidad: `{pos['amount']}`\n"
            f"• Stop Loss: `${pos['stop_loss']:,.2f}`\n"
            f"• Take Profit: `${pos['take_profit']:,.2f}`\n"
            f"• Hora: `{pos['entry_time']}`"
        )
        logger.info(f"[ALERTA POSICION ABIERTA] {pos['symbol']} a ${pos['entry_price']:,.2f}")
        self.broadcast(msg)

    def notify_position_closed(self, trade: Dict[str, Any]):
        icon = "🟢" if trade["net_pnl"] >= 0 else "🔴"
        msg = (
            f"{icon} *POSICIÓN CERRADA*\n"
            f"• Par: `{trade['symbol']}`\n"
            f"• Motivo: `{trade['exit_reason']}`\n"
            f"• Entrada: `${trade['entry_price']:,.2f}` ➔ Salida: `${trade['exit_price']:,.2f}`\n"
            f"• PnL Neto: `${trade['net_pnl']:+,.2f}` ({trade['return_pct']:+.2f}%)\n"
            f"• Hora: `{trade['exit_time']}`"
        )
        logger.info(f"[ALERTA POSICION CERRADA] {trade['symbol']} | PnL: ${trade['net_pnl']:+,.2f}")
        self.broadcast(msg)

    def notify_circuit_breaker(self, reason: str):
        msg = f"🚨 *CIRCUIT BREAKER ACTIVADO*\n{reason}\nEl bot ha pausado nuevas entradas para proteger el capital."
        logger.warning(f"[ALERTA CIRCUIT BREAKER] {reason}")
        self.broadcast(msg)
