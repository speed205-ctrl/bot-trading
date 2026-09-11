"""Generates In-Sample vs Out-of-Sample validation and Walk-Forward reports."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.optimizer.walk_forward import WalkForwardWindow
from src.utils.helpers import format_currency, format_pct, safe_div
from src.utils.logger import setup_logger

logger = setup_logger("ValidationReport")


class ValidationReportGenerator:
    """Evaluates overfitting, out-of-sample degradation, and walk-forward stability."""

    def __init__(self, output_dir: str = "results/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        strategy_name: str,
        in_sample_report: Dict[str, Any],
        out_of_sample_report: Dict[str, Any],
        walk_forward_windows: Optional[List[WalkForwardWindow]] = None,
        best_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculates degradation metrics and determines final bot-readiness verdict."""
        m_is = in_sample_report["metrics"]
        m_oos = out_of_sample_report["metrics"]

        # Degradation calculations
        pf_is = m_is["profit_factor"]
        pf_oos = m_oos["profit_factor"]
        pf_degradation = safe_div(pf_is - pf_oos, pf_is, default=0.0)

        sharpe_is = m_is["sharpe_ratio"]
        sharpe_oos = m_oos["sharpe_ratio"]
        sharpe_degradation = safe_div(sharpe_is - sharpe_oos, sharpe_is, default=0.0)

        dd_is = m_is["max_drawdown_pct"]
        dd_oos = m_oos["max_drawdown_pct"]
        dd_increase = safe_div(dd_oos - dd_is, dd_is, default=0.0)

        # Overfitting flags per spec Section 7.3 & Section 8
        overfitting_alerts = []
        if pf_degradation > 0.40:
            overfitting_alerts.append(f"Degradación de Profit Factor excesiva: {format_pct(pf_degradation)} (> 40%)")
        if sharpe_degradation > 0.40:
            overfitting_alerts.append(f"Degradación de Sharpe excesiva: {format_pct(sharpe_degradation)} (> 40%)")
        if dd_increase > 0.25:
            overfitting_alerts.append(f"Drawdown Out-of-Sample superó al In-Sample por más del 25%: {format_pct(dd_increase)}")

        # Walk-forward consistency evaluation
        wf_stats = {}
        wf_passed = True
        if walk_forward_windows:
            total_w = len(walk_forward_windows)
            passed_w = sum(1 for w in walk_forward_windows if w.passed)
            failed_equity = any(w.test_return_pct <= -1.0 for w in walk_forward_windows)

            pass_rate = safe_div(passed_w, total_w, default=0.0)
            wf_passed = bool(passed_w >= min(4, total_w) and not failed_equity)

            wf_stats = {
                "total_windows": total_w,
                "passed_windows": passed_w,
                "pass_rate": pass_rate,
                "total_loss_occurred": failed_equity,
                "wf_criteria_passed": wf_passed,
            }
            if not wf_passed:
                overfitting_alerts.append(f"Walk-Forward inestable: sólo {passed_w}/{total_w} ventanas mantuvieron Profit Factor > 1.0")

        # Final Acceptance Verdict
        is_verdict_pass = in_sample_report.get("verdict") == "PASA"
        oos_verdict_pass = out_of_sample_report.get("verdict") == "PASA"
        no_overfitting = len(overfitting_alerts) == 0

        final_verdict = "APROBADA PARA FASE 2 (BOT)" if (is_verdict_pass and oos_verdict_pass and no_overfitting and wf_passed) else "DESCARTADA"

        # Build Markdown document
        clean_name = strategy_name.lower().replace(" ", "_")
        md_lines = [
            f"# Reporte de Validación Final: {strategy_name}",
            f"### Veredicto Global: **{final_verdict}**",
            "",
            "## 1. Parámetros Optimizados",
            "```json",
            json.dumps(best_params or {}, indent=2),
            "```",
            "",
            "## 2. Comparativa In-Sample vs Out-of-Sample",
            "| Métrica | In-Sample (2021-2023) | Out-of-Sample (2024) | Degradación / Cambio | Límite Máximo | Estado |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
            f"| Profit Factor | {pf_is:.2f} | {pf_oos:.2f} | {format_pct(pf_degradation)} | <= 40% | {'✅ OK' if pf_degradation <= 0.40 else '❌ SOBREAJUSTE'} |",
            f"| Ratio de Sharpe | {sharpe_is:.2f} | {sharpe_oos:.2f} | {format_pct(sharpe_degradation)} | <= 40% | {'✅ OK' if sharpe_degradation <= 0.40 else '❌ SOBREAJUSTE'} |",
            f"| Máximo Drawdown | {format_pct(dd_is)} | {format_pct(dd_oos)} | {format_pct(dd_increase)} | <= +25% | {'✅ OK' if dd_increase <= 0.25 else '❌ ALTO RIESGO'} |",
            f"| Win Rate | {format_pct(m_is['win_rate_pct'])} | {format_pct(m_oos['win_rate_pct'])} | - | - | Informativo |",
            f"| Total Operaciones | {m_is['total_trades']} | {m_oos['total_trades']} | - | - | Informativo |",
            "",
            "## 3. Criterios de Aprobación por Periodo",
            f"- **In-Sample:** {in_sample_report.get('verdict')}",
            f"- **Out-of-Sample:** {out_of_sample_report.get('verdict')}",
            f"- **Sobreoptimización:** {'Detectada (' + str(len(overfitting_alerts)) + ' alertas)' if overfitting_alerts else 'No detectada (Robusta)'}",
        ]

        if overfitting_alerts:
            md_lines.extend(["", "### Alertas de Sobreajuste:"])
            for alert in overfitting_alerts:
                md_lines.append(f"- ⚠️ {alert}")

        if walk_forward_windows:
            md_lines.extend([
                "",
                "## 4. Análisis Walk-Forward (Ventanas Rodantes)",
                f"**Resultado WF:** {'✅ Cumple consistencia (>= 4 de 6)' if wf_passed else '❌ No cumple consistencia'}",
                "| Ventana | Periodo Entrenamiento | Periodo Prueba | PF Train | PF Test | Trades Test | Retorno Test | Max DD | Estado |",
                "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
            ])
            for w in walk_forward_windows:
                status_icon = "🟢 PASA" if w.passed else "🔴 FALLA"
                md_lines.append(
                    f"| {w.window_index} | {w.train_start.date()} a {w.train_end.date()} | {w.test_start.date()} a {w.test_end.date()} | {w.train_profit_factor:.2f} | {w.test_profit_factor:.2f} | {w.test_trades} | {format_pct(w.test_return_pct)} | {format_pct(w.test_max_drawdown_pct)} | {status_icon} |"
                )

        md_content = "\n".join(md_lines)
        md_file = self.output_dir / f"validation_{clean_name}.md"
        json_file = self.output_dir / f"validation_{clean_name}.json"

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        summary_dict = {
            "strategy_name": strategy_name,
            "final_verdict": final_verdict,
            "best_params": best_params,
            "in_sample": in_sample_report,
            "out_of_sample": out_of_sample_report,
            "degradation": {
                "profit_factor_degradation": pf_degradation,
                "sharpe_degradation": sharpe_degradation,
                "drawdown_increase": dd_increase,
            },
            "overfitting_alerts": overfitting_alerts,
            "walk_forward": wf_stats,
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(summary_dict, f, indent=2, default=str)

        logger.info(f"Generated validation report: {md_file}")
        return summary_dict
