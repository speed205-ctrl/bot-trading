"""Generates visual charts (PNG) for equity curves and drawdowns."""
from pathlib import Path
from typing import Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless execution
import matplotlib.pyplot as plt
import pandas as pd

from src.utils.logger import setup_logger

logger = setup_logger("ChartGenerator")


def plot_equity_and_drawdown(
    equity_curve: pd.DataFrame,
    strategy_name: str,
    output_path: Optional[str] = None
) -> Path:
    """Creates a two-panel chart of Equity Curve and Underwater Drawdown and saves to PNG."""
    if equity_curve.empty:
        raise ValueError("Equity curve is empty, cannot generate plot.")

    clean_name = strategy_name.lower().replace(" ", "_")
    target_file = Path(output_path or f"results/reports/equity_{clean_name}.png")
    target_file.parent.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(12, 7),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]}
    )

    # Panel 1: Equity Curve
    ax1.plot(equity_curve.index, equity_curve["equity"], color="#1f77b4", linewidth=1.5, label="Equity ($)")
    if "peak_equity" in equity_curve.columns:
        ax1.plot(equity_curve.index, equity_curve["peak_equity"], color="#2ca02c", linestyle="--", alpha=0.6, label="High Water Mark")

    ax1.set_title(f"Laboratorio de Trading - Equity Curve: {strategy_name}", fontsize=13, fontweight="bold", pad=10)
    ax1.set_ylabel("Balance ($)", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper left")

    # Panel 2: Drawdown Underwater
    dd_pct = equity_curve["drawdown_pct"] * 100.0
    ax2.fill_between(equity_curve.index, -dd_pct, 0, color="#d62728", alpha=0.4, label="Drawdown (%)")
    ax2.plot(equity_curve.index, -dd_pct, color="#d62728", linewidth=1.0)
    ax2.set_ylabel("Drawdown (%)", fontsize=10)
    ax2.set_xlabel("Fecha", fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="lower left")

    plt.tight_layout()
    plt.savefig(target_file, dpi=150)
    plt.close(fig)

    logger.info(f"Saved performance chart to: {target_file}")
    return target_file
