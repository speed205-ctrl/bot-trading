"""Generates comparative rankings and summary reports across multiple strategies."""
import json
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
from tabulate import tabulate

from src.utils.helpers import format_currency, format_pct
from src.utils.logger import setup_logger

logger = setup_logger("ComparativeReport")


class ComparativeReportGenerator:
    """Generates comparative ranking tables and selection analysis."""

    def __init__(self, output_dir: str = "results/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, reports_data: List[Dict[str, Any]], period_type: str = "in_sample") -> Dict[str, Any]:
        """Consolidates individual strategy reports into a comparative matrix."""
        if not reports_data:
            raise ValueError("No strategy report data provided for comparison.")

        rows = []
        for rep in reports_data:
            m = rep["metrics"]
            rows.append({
                "Estrategia": rep["strategy_name"],
                "Veredicto": rep["verdict"],
                "Profit Factor": m["profit_factor"],
                "Sharpe": m["sharpe_ratio"],
                "Max Drawdown": m["max_drawdown_pct"],
                "Retorno Total": m["total_return_pct"],
                "Win Rate": m["win_rate_pct"],
                "Operaciones": m["total_trades"],
                "Comisiones": m["total_commissions"],
            })

        df = pd.DataFrame(rows)

        # Rankings
        rank_pf = df.sort_values(by="Profit Factor", ascending=False)
        rank_sharpe = df.sort_values(by="Sharpe", ascending=False)
        rank_dd = df.sort_values(by="Max Drawdown", ascending=True)

        passed = df[df["Veredicto"] == "PASA"]
        discarded = df[df["Veredicto"] == "NO PASA"]

        # Build Markdown
        md_lines = [
            f"# Reporte Comparativo de Estrategias ({period_type.upper()})",
            "",
            "## 1. Matriz General de Desempeño",
            "| Estrategia | Veredicto | Profit Factor | Sharpe | Max DD | Retorno Total | Win Rate | Trades |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for _, r in df.iterrows():
            badge = "🟢 PASA" if r["Veredicto"] == "PASA" else "🔴 DESCARTADA"
            md_lines.append(
                f"| **{r['Estrategia']}** | {badge} | {r['Profit Factor']:.2f} | {r['Sharpe']:.2f} | {format_pct(r['Max Drawdown'])} | {format_pct(r['Retorno Total'])} | {format_pct(r['Win Rate'])} | {r['Operaciones']} |"
            )

        md_lines.extend([
            "",
            "## 2. Rankings por Métrica Clave",
            "### Top por Profit Factor:",
        ])
        for idx, (_, r) in enumerate(rank_pf.iterrows(), 1):
            md_lines.append(f"{idx}. **{r['Estrategia']}**: {r['Profit Factor']:.2f}")

        md_lines.append("\n### Top por Ratio de Sharpe:")
        for idx, (_, r) in enumerate(rank_sharpe.iterrows(), 1):
            md_lines.append(f"{idx}. **{r['Estrategia']}**: {r['Sharpe']:.2f}")

        md_lines.append("\n### Menor Drawdown (Menor Riesgo):")
        for idx, (_, r) in enumerate(rank_dd.iterrows(), 1):
            md_lines.append(f"{idx}. **{r['Estrategia']}**: {format_pct(r['Max Drawdown'])}")

        md_lines.extend([
            "",
            "## 3. Resumen de Selección",
            f"- **Estrategias Aprobadas ({len(passed)}):** {', '.join(passed['Estrategia'].tolist()) if not passed.empty else 'Ninguna'}",
            f"- **Estrategias Descartadas ({len(discarded)}):** {', '.join(discarded['Estrategia'].tolist()) if not discarded.empty else 'Ninguna'}",
        ])

        md_content = "\n".join(md_lines)
        md_file = self.output_dir / f"comparative_report_{period_type}.md"
        json_file = self.output_dir / f"comparative_report_{period_type}.json"

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        summary_dict = {
            "period_type": period_type,
            "total_evaluated": len(df),
            "approved_count": len(passed),
            "discarded_count": len(discarded),
            "strategies": rows
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(summary_dict, f, indent=2, default=str)

        logger.info(f"Saved comparative report to: {md_file}")
        return summary_dict
