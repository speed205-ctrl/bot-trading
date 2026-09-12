"""Logging setup for the Strategy Lab."""
import logging
import sys
from pathlib import Path


def setup_logger(name: str = "StrategyLab", level: int = logging.INFO, log_to_file: bool = False) -> logging.Logger:
    """Configures and returns a standard logger with formatting."""
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # File Handler
    if log_to_file:
        logs_dir = Path("results/reports")
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(logs_dir / "strategy_lab.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    return logger
