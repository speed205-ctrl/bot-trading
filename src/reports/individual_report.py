"""Generates individual strategy reports in Console, Markdown, and JSON formats."""
import json
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
from tabulate import tabulate

from src.backtest.engine import BacktestResult
from src.metrics import calculate_all_metrics
from src.reports.chart_generator import plot_equity_and_drawdown
from src.utils.helpers import format_currency, format_pct
from src.utils.logger import setup_logger

logger = setup_logger("IndividualReport")


class IndividualReportGenerator:
    """Generates detailed individual strategy report."""

    def __init__(self, output_dir: str = "results/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        result: BacktestResult,
        period_type: str = "in_sample",
        strategy_params: Optional[Dict[str, Any]] = None,
        save_plots: bool = True
    ) -> Dict[str, Any]:
        """Calculates metrics, renders console, markdown, JSON, and saves files."""
        report_data = calculate_all_metrics(result, period_type=period_type)
        m = report_data["metrics"]
        clean_name = result.strategy_name.lower().replace(" ", "_")

        # 1. Generate PNG Chart
        chart_path = None
        if save_plots and not result.equity_curve.empty:
            chart_file = self.output_dir / f"chart_{clean_name}.png"
            chart_path = str(plot_equity_and_drawdown(result.equity_curve, result.strategy_name, str(chart_file)))

        report_data["chart_path"] = chart_path
        report_data["strategy_params"] = strategy_params or {}

        # 2. Build Markdown content
        md_lines = [
            f"# Reporte de Estrategia: {result.strategy_name}",
            f"**Perfil de Riesgo:** {result.risk_profile_name} | **Activo:** {result.symbol} | **Timeframe:** {result.timeframe} | **Periodo:** {period_type.upper()}",
            f"### Veredicto: **{report_data['verdict']}**",
            "",
            "## 1. Parámetros Utilizados",
            "```json",
            json.dumps(strategy_params or {}, indent=2),
            "```",
            "",
            "## 2. Métricas de Rendimiento y Riesgo",
            "| Métrica | Valor |",
            "| :--- | :--- |",
            f"| Capital Inicial | {format_currency(m['initial_capital'])} |",
            f"| Capital Final | {format_currency(m['final_equity'])} |",
            f"| Retorno Total | {format_pct(m['total_return_pct'])} |",
            f"| Retorno Anualizado | {format_pct(m['annualized_return_pct'])} |",
            f"| Profit Factor | {m['profit_factor']:.2f} |",
            f"| Ratio de Sharpe | {m['sharpe_ratio']:.2f} |",
            f"| Ratio de Sortino | {m['sortino_ratio']:.2f} |",
            f"| Ratio de Calmar | {m['calmar_ratio']:.2f} |",
            f"| Máximo Drawdown (%) | {format_pct(m['max_drawdown_pct'])} |",
            f"| Máximo Drawdown ($) | {format_currency(m['max_drawdown_abs'])} |",
            f"| Duración Máx Drawdown | {m['drawdown_duration_days']:.1f} días |",
            f"| Volatilidad Anualizada | {format_pct(m['annualized_volatility'])} |",
            f"| Value at Risk (VaR 95% diario) | {format_pct(m['var_95_daily'])} |",
            f"| Total de Operaciones | {m['total_trades']} |",
            f"| Win Rate | {format_pct(m['win_rate_pct'])} |",
            f"| Ratio Riesgo/Beneficio | {m['risk_reward_ratio']:.2f} |",
            f"| Pérdidas Consecutivas Máx | {m['max_consecutive_losses']} |",
            f"| Duración Promedio Operación | {m['avg_trade_duration_hours']:.1f} horas |",
            f"| Frecuencia Operaciones/Semana | {m['trades_per_week']:.1f} |",
            f"| Comisiones Totales | {format_currency(m['total_commissions'])} |",
            f"| Slippage Estimado | {format_currency(m['total_slippage'])} |",
            f"| Impacto de Costos en Capital | {format_pct(m['cost_impact_pct'])} |",
            "",
            "## 3. Criterios de Aprobación (Sección 8)",
            "| Criterio | Exigencia | Resultado | Estado |",
            "| :--- | :--- | :--- | :--- |",
        ]

        if period_type.lower() == "in_sample":
            md_lines.extend([
                f"| Profit Factor | > 1.3 | {m['profit_factor']:.2f} | {'✅ CUMPLE' if report_data['criteria']['profit_factor_gt_1_3'] else '❌ FALLA'} |",
                f"| Máximo Drawdown | < 20% | {format_pct(m['max_drawdown_pct'])} | {'✅ CUMPLE' if report_data['criteria']['max_drawdown_lt_20pct'] else '❌ FALLA'} |",
                f"| Win Rate | > 40% | {format_pct(m['win_rate_pct'])} | {'✅ CUMPLE' if report_data['criteria']['win_rate_gt_40pct'] else '❌ FALLA'} |",
                f"| Total Operaciones | > 100 | {m['total_trades']} | {'✅ CUMPLE' if report_data['criteria']['total_trades_gt_100'] else '❌ FALLA'} |",
                f"| Ratio de Sharpe | > 1.0 | {m['sharpe_ratio']:.2f} | {'✅ CUMPLE' if report_data['criteria']['sharpe_gt_1_0'] else '❌ FALLA'} |",
                f"| Retorno Neto | > 0% | {format_pct(m['total_return_pct'])} | {'✅ CUMPLE' if report_data['criteria']['total_return_positive'] else '❌ FALLA'} |",
            ])
        else:
            md_lines.extend([
                f"| Profit Factor | > 1.1 | {m['profit_factor']:.2f} | {'✅ CUMPLE' if report_data['criteria']['profit_factor_gt_1_1'] else '❌ FALLA'} |",
                f"| Máximo Drawdown | < 25% | {format_pct(m['max_drawdown_pct'])} | {'✅ CUMPLE' if report_data['criteria']['max_drawdown_lt_25pct'] else '❌ FALLA'} |",
                f"| Win Rate | > 35% | {format_pct(m['win_rate_pct'])} | {'✅ CUMPLE' if report_data['criteria']['win_rate_gt_35pct'] else '❌ FALLA'} |",
                f"| Total Operaciones | > 30 | {m['total_trades']} | {'✅ CUMPLE' if report_data['criteria']['total_trades_gt_30'] else '❌ FALLA'} |",
                f"| Ratio de Sharpe | > 0.8 | {m['sharpe_ratio']:.2f} | {'✅ CUMPLE' if report_data['criteria']['sharpe_gt_0_8'] else '❌ FALLA'} |",
                f"| Retorno Neto | > 0% | {format_pct(m['total_return_pct'])} | {'✅ CUMPLE' if report_data['criteria']['total_return_positive'] else '❌ FALLA'} |",
            ])

        if report_data["warnings"]:
            md_lines.extend(["", "### Advertencias Detectadas:"])
            for w in report_data["warnings"]:
                md_lines.append(f"- ⚠️ {w}")

        if chart_path:
            md_lines.extend(["", f"![Equity Chart]({chart_path})"])

        md_content = "\n".join(md_lines)

        # 3. Save Markdown and JSON
        md_file = self.output_dir / f"report_{clean_name}_{period_type}.md"
        json_file = self.output_dir / f"report_{clean_name}_{period_type}.json"

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        # Exclude un-serializable objects from JSON dump
        json_dict = {k: v for k, v in report_data.items() if k != "trades"}
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_dict, f, indent=2)

        logger.info(f"Generated report for {result.strategy_name}: {md_file}")
        return report_data
