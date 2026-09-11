"""Unit tests for metrics calculations and report generators."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestResult
from src.backtest.order_simulator import Trade
from src.metrics import calculate_all_metrics
from src.metrics.performance_metrics import calculate_performance_metrics
from src.metrics.risk_metrics import calculate_risk_metrics
from src.metrics.trade_statistics import calculate_trade_statistics
from src.reports.comparative_report import ComparativeReportGenerator
from src.reports.individual_report import IndividualReportGenerator


@pytest.fixture
def mock_trades():
    """Returns synthetic closed trades with known wins and losses."""
    t1 = Trade("BTC/USDT", "long", pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02"), 20000, 21000, 1.0, 21000, 1000, 980, 20, 5, 0.05, "take_profit", 24)
    t2 = Trade("BTC/USDT", "long", pd.Timestamp("2023-01-03"), pd.Timestamp("2023-01-04"), 21000, 20500, 1.0, 20500, -500, -520, 20, 5, -0.025, "stop_loss", 24)
    t3 = Trade("BTC/USDT", "long", pd.Timestamp("2023-01-05"), pd.Timestamp("2023-01-06"), 20500, 20000, 1.0, 20000, -500, -520, 20, 5, -0.025, "stop_loss", 24)
    return [t1, t2, t3]


@pytest.fixture
def mock_equity_curve():
    """Generates synthetic equity curve with a known drawdown."""
    dates = pd.date_range("2023-01-01", periods=100, freq="1h", tz="UTC")
    # Start at 10000, grow to 12000, dip to 10800 (10% DD), finish at 13000
    equity = np.concatenate([
        np.linspace(10000, 12000, 40),
        np.linspace(12000, 10800, 30),
        np.linspace(10800, 13000, 30),
    ])
    df = pd.DataFrame({"equity": equity}, index=dates)
    return df


def test_performance_metrics(mock_trades, mock_equity_curve):
    """Verifies performance calculations."""
    perf = calculate_performance_metrics(10000.0, mock_equity_curve, mock_trades)

    assert perf["initial_capital"] == 10000.0
    assert perf["final_equity"] == 13000.0
    assert pytest.approx(perf["total_return_pct"], rel=1e-3) == 0.30  # 30% return
    # Win = 980, Loss = 1040. Profit factor = 980 / 1040 = ~0.942
    assert pytest.approx(perf["profit_factor"], rel=1e-2) == 0.94


def test_risk_metrics(mock_trades, mock_equity_curve):
    """Verifies drawdown and risk metrics."""
    risk = calculate_risk_metrics(mock_equity_curve, mock_trades)

    # 12000 peak down to 10800 -> 1200 drop = 10% drawdown
    assert pytest.approx(risk["max_drawdown_pct"], rel=1e-2) == 0.10
    assert pytest.approx(risk["max_drawdown_abs"], rel=1e-2) == 1200.0
    # Two consecutive losses in mock_trades
    assert risk["max_consecutive_losses"] == 2


def test_trade_statistics(mock_trades):
    """Verifies trade counts, win rate, and cost impact."""
    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2023-01-07")
    stats = calculate_trade_statistics(mock_trades, start, end, 10000.0)

    assert stats["total_trades"] == 3
    assert stats["winning_trades"] == 1
    assert stats["losing_trades"] == 2
    assert pytest.approx(stats["win_rate_pct"], rel=1e-3) == 1.0 / 3.0
    assert stats["total_commissions"] == 60.0


def test_reports_generation(mock_trades, mock_equity_curve, tmp_path):
    """Tests that individual and comparative reports write markdown, json, and png files."""
    peak = mock_equity_curve["equity"].cummax()
    mock_equity_curve["drawdown_pct"] = (peak - mock_equity_curve["equity"]) / peak
    mock_equity_curve["peak_equity"] = peak

    result = BacktestResult(
        strategy_name="Test Strategy",
        risk_profile_name="Perfil Moderado",
        symbol="BTC/USDT",
        timeframe="1h",
        initial_capital=10000.0,
        final_equity=13000.0,
        trades=mock_trades,
        equity_curve=mock_equity_curve
    )

    ind_gen = IndividualReportGenerator(output_dir=str(tmp_path))
    report_data = ind_gen.generate(result, period_type="in_sample", save_plots=True)

    assert report_data["verdict"] in ["PASA", "NO PASA"]
    # Check generated files
    assert (tmp_path / "chart_test_strategy.png").exists()
    assert (tmp_path / "report_test_strategy_in_sample.md").exists()
    assert (tmp_path / "report_test_strategy_in_sample.json").exists()

    # Comparative report test
    comp_gen = ComparativeReportGenerator(output_dir=str(tmp_path))
    comp_res = comp_gen.generate([report_data], period_type="in_sample")
    assert comp_res["total_evaluated"] == 1
    assert (tmp_path / "comparative_report_in_sample.md").exists()
    assert (tmp_path / "comparative_report_in_sample.json").exists()
