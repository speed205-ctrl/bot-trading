"""Unit tests for optimizer, walk-forward analysis, and validation reporting."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.optimizer.grid_search import GridSearchOptimizer
from src.optimizer.random_search import RandomSearchOptimizer
from src.optimizer.walk_forward import WalkForwardAnalyzer, WalkForwardWindow
from src.reports.validation_report import ValidationReportGenerator
from src.strategies.trend_pullback_atr import TrendPullbackATRStrategy


@pytest.fixture
def test_dataset():
    """Generates synthetic multi-month hourly OHLCV dataset."""
    np.random.seed(99)
    n = 600  # ~25 days of hourly candles
    dates = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    trend = np.linspace(18000, 24000, n)
    noise = np.sin(np.linspace(0, 16 * np.pi, n)) * 400
    close = trend + noise
    high = close + np.random.uniform(50, 200, n)
    low = close - np.random.uniform(50, 200, n)
    open_p = (high + low) / 2.0
    volume = np.random.uniform(500, 2500, n)

    df = pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    return df


def test_grid_search_optimizer(test_dataset):
    """Tests grid search parameter exploration."""
    optimizer = GridSearchOptimizer(
        target_metric="profit_factor",
        max_combinations=4,
        min_trades=0  # allow any count for fast test
    )
    custom_ranges = {
        "rsi_oversold": [25, 30],
        "atr_sl_mult": [2.0, 2.5]
    }
    results = optimizer.optimize(TrendPullbackATRStrategy, test_dataset, param_ranges=custom_ranges)

    assert len(results) <= 4
    if len(results) > 1:
        assert results[0].target_value >= results[1].target_value


def test_random_search_optimizer(test_dataset):
    """Tests random search optimizer."""
    optimizer = RandomSearchOptimizer(
        target_metric="profit_factor",
        max_combinations=3,
        min_trades=0
    )
    custom_ranges = {
        "rsi_oversold": [25, 30, 35],
        "atr_sl_mult": [1.5, 2.0, 2.5],
        "atr_tp_mult": [2.0, 3.0, 4.0]
    }
    results = optimizer.optimize(TrendPullbackATRStrategy, test_dataset, param_ranges=custom_ranges)
    assert len(results) <= 3


def test_validation_report_generator(tmp_path):
    """Verifies degradation calculation, overfitting detection, and report generation."""
    generator = ValidationReportGenerator(output_dir=str(tmp_path))

    in_sample_report = {
        "strategy_name": "Trend Pullback ATR",
        "verdict": "PASA",
        "metrics": {
            "profit_factor": 2.0,
            "sharpe_ratio": 1.5,
            "max_drawdown_pct": 0.12,
            "win_rate_pct": 0.45,
            "total_trades": 120,
            "final_equity": 15000.0,
        }
    }

    # Out of sample with 50% degradation in PF (2.0 -> 1.0), triggering overfitting alert!
    out_of_sample_report = {
        "strategy_name": "Trend Pullback ATR",
        "verdict": "NO PASA",
        "metrics": {
            "profit_factor": 1.0,
            "sharpe_ratio": 0.6,
            "max_drawdown_pct": 0.18,
            "win_rate_pct": 0.36,
            "total_trades": 35,
            "final_equity": 10500.0,
        }
    }

    summary = generator.generate(
        strategy_name="Trend Pullback ATR",
        in_sample_report=in_sample_report,
        out_of_sample_report=out_of_sample_report,
        best_params={"rsi_oversold": 30}
    )

    assert summary["final_verdict"] == "DESCARTADA"
    assert len(summary["overfitting_alerts"]) > 0
    assert (tmp_path / "validation_trend_pullback_atr.md").exists()
    assert (tmp_path / "validation_trend_pullback_atr.json").exists()
