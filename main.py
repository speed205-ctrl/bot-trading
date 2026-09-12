"""CLI unified interface for the Strategy Lab (Laboratorio de Estrategias de Trading)."""
import argparse
import sys
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from tabulate import tabulate

from src.backtest.engine import BacktestEngine
from src.data.downloader import BinanceDownloader
from src.optimizer.grid_search import GridSearchOptimizer
from src.optimizer.random_search import RandomSearchOptimizer
from src.optimizer.walk_forward import WalkForwardAnalyzer
from src.reports.comparative_report import ComparativeReportGenerator
from src.reports.individual_report import IndividualReportGenerator
from src.reports.validation_report import ValidationReportGenerator
from src.strategies import STRATEGY_REGISTRY, get_strategy
from src.utils.config_loader import config
from src.utils.logger import setup_logger

logger = setup_logger("StrategyLabCLI")


def cmd_download(args):
    """Downloads and caches historical market data from Binance."""
    downloader = BinanceDownloader(cache_dir=config.settings["data"]["raw_dir"])
    symbol = args.symbol or config.settings["exchange"]["default_pair"]
    timeframe = args.timeframe or config.settings["exchange"]["default_timeframe"]
    start_date = args.start or config.settings["data"]["in_sample_start"]
    end_date = args.end or config.settings["data"]["out_of_sample_end"]
    market_type = args.market or config.settings["exchange"]["trading_mode"]

    print(f"\n📥 Descargando datos para {symbol} [{timeframe}] ({market_type}) de {start_date} a {end_date}...")
    df, meta = downloader.download_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        market_type=market_type,
        use_cache=not args.no_cache
    )
    print(f"✅ Descarga completada: {len(df)} velas validadas en caché.")
    print(f"   Gaps detectados: {meta.get('gaps_detected', 0)} | Gaps rellenados: {meta.get('gaps_filled', 0)}")


def cmd_backtest(args):
    """Executes backtests on historical data."""
    downloader = BinanceDownloader(cache_dir=config.settings["data"]["raw_dir"])
    symbol = args.symbol or config.settings["exchange"]["default_pair"]
    timeframe = args.timeframe or config.settings["exchange"]["default_timeframe"]
    start_date = args.start or config.settings["data"]["in_sample_start"]
    end_date = args.end or config.settings["data"]["in_sample_end"]
    profile = args.profile or config.settings["backtest"]["default_risk_profile"]

    df, _ = downloader.download_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        market_type=config.settings["exchange"]["trading_mode"]
    )

    strategies_to_test = [args.strategy] if args.strategy else list(STRATEGY_REGISTRY.keys())
    engine = BacktestEngine(
        initial_capital=config.settings["backtest"]["initial_capital"],
        risk_profile=profile,
        commission_rate=config.settings["backtest"]["commission_rate"],
        slippage_pct=config.settings["backtest"]["slippage_pct"]
    )
    rep_gen = IndividualReportGenerator(output_dir=config.settings["reports"]["output_dir"])
    comp_gen = ComparativeReportGenerator(output_dir=config.settings["reports"]["output_dir"])

    reports_data = []
    print(f"\n🚀 Iniciando Backtest en {symbol} [{timeframe}] con perfil: {profile.upper()} ({start_date} a {end_date})...\n")

    for s_id in strategies_to_test:
        strat = get_strategy(s_id)
        res = engine.run(strat, df, symbol=symbol)
        rep = rep_gen.generate(res, period_type="in_sample", strategy_params=strat.parameters)
        reports_data.append(rep)

        m = rep["metrics"]
        badge = "🟢 PASA" if rep["verdict"] == "PASA" else "🔴 NO PASA"
        print(f"▶ {strat.name:<32} | Veredicto: {badge:<10} | PF: {m['profit_factor']:<5.2f} | Sharpe: {m['sharpe_ratio']:<5.2f} | DD: {m['max_drawdown_pct']*100:<5.1f}% | Trades: {m['total_trades']}")

    if len(reports_data) > 1:
        comp_gen.generate(reports_data, period_type="in_sample")
        print(f"\n📊 Reporte comparativo generado en: {config.settings['reports']['output_dir']}/comparative_report_in_sample.md")


def cmd_optimize(args):
    """Executes parameter optimization on In-Sample data."""
    downloader = BinanceDownloader(cache_dir=config.settings["data"]["raw_dir"])
    symbol = args.symbol or config.settings["exchange"]["default_pair"]
    timeframe = args.timeframe or config.settings["exchange"]["default_timeframe"]
    start_date = config.settings["data"]["in_sample_start"]
    end_date = config.settings["data"]["in_sample_end"]
    profile = args.profile or config.settings["backtest"]["default_risk_profile"]

    strategy_id = args.strategy
    if not strategy_id:
        print("❌ Error: Debes especificar una estrategia para optimizar (--strategy).")
        sys.exit(1)

    df, _ = downloader.download_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        market_type=config.settings["exchange"]["trading_mode"]
    )

    strat_cls = STRATEGY_REGISTRY[strategy_id]
    method = args.method or config.settings["optimization"]["method"]

    if method == "random":
        optimizer = RandomSearchOptimizer(
            target_metric=config.settings["optimization"]["target_metric"],
            max_combinations=args.max_combos or config.settings["optimization"]["max_combinations"],
            risk_profile=profile
        )
    else:
        optimizer = GridSearchOptimizer(
            target_metric=config.settings["optimization"]["target_metric"],
            max_combinations=args.max_combos or config.settings["optimization"]["max_combinations"],
            risk_profile=profile
        )

    print(f"\n🔍 Optimizando '{strategy_id}' usando {method.upper()} sobre datos In-Sample ({start_date} a {end_date})...")
    results = optimizer.optimize(strat_cls, df, symbol=symbol)

    if not results:
        print("⚠️ Ninguna combinación produjo el mínimo de 30 operaciones requeridas.")
        return

    best = results[0]
    print(f"\n🏆 Mejor combinación encontrada para {strategy_id}:")
    print(f"   Parámetros: {best.parameters}")
    print(f"   Profit Factor: {best.profit_factor:.2f} | Sharpe: {best.sharpe_ratio:.2f} | Max DD: {best.max_drawdown_pct*100:.1f}% | Trades: {best.total_trades}")


def cmd_walk_forward(args):
    """Runs rolling Walk-Forward analysis."""
    downloader = BinanceDownloader(cache_dir=config.settings["data"]["raw_dir"])
    symbol = args.symbol or config.settings["exchange"]["default_pair"]
    timeframe = args.timeframe or config.settings["exchange"]["default_timeframe"]
    start_date = config.settings["data"]["in_sample_start"]
    end_date = config.settings["data"]["out_of_sample_end"]
    profile = args.profile or config.settings["backtest"]["default_risk_profile"]

    strategy_id = args.strategy
    if not strategy_id:
        print("❌ Error: Debes especificar una estrategia (--strategy).")
        sys.exit(1)

    df, _ = downloader.download_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        market_type=config.settings["exchange"]["trading_mode"]
    )

    strat_cls = STRATEGY_REGISTRY[strategy_id]
    analyzer = WalkForwardAnalyzer(
        train_months=config.settings["walk_forward"]["train_months"],
        test_months=config.settings["walk_forward"]["test_months"],
        step_months=config.settings["walk_forward"]["step_months"],
        risk_profile=profile
    )

    print(f"\n🔄 Ejecutando Walk-Forward para '{strategy_id}' sobre periodo total ({start_date} a {end_date})...")
    windows = analyzer.run(strat_cls, df, symbol=symbol, max_optim_combos=20)

    passed_count = sum(1 for w in windows if w.passed)
    print(f"\n📈 Resultados Walk-Forward ({passed_count}/{len(windows)} ventanas aprobadas):")
    for w in windows:
        icon = "🟢" if w.passed else "🔴"
        print(f"   {icon} Ventana {w.window_index}: Test [{w.test_start.date()} a {w.test_end.date()}] | PF: {w.test_profit_factor:.2f} | Trades: {w.test_trades} | DD: {w.test_max_drawdown_pct*100:.1f}%")


def cmd_run_all(args):
    """Executes complete laboratory lifecycle end-to-end."""
    print("================================================================================")
    print("       LABORATORIO DE ESTRATEGIAS DE TRADING - CICLO COMPLETO E2E               ")
    print("================================================================================\n")

    # Step 1: Data Download
    print("--- [PASO 1/5] Descargando y validando histórico de Binance ---")
    downloader = BinanceDownloader(cache_dir=config.settings["data"]["raw_dir"])
    symbol = args.symbol or config.settings["exchange"]["default_pair"]
    timeframe = args.timeframe or config.settings["exchange"]["default_timeframe"]
    is_start = config.settings["data"]["in_sample_start"]
    is_end = config.settings["data"]["in_sample_end"]
    oos_start = config.settings["data"]["out_of_sample_start"]
    oos_end = config.settings["data"]["out_of_sample_end"]

    df, _ = downloader.download_ohlcv(symbol, timeframe, is_start, oos_end, market_type="futures")
    df_is = df[(df.index >= pd.to_datetime(is_start, utc=True)) & (df.index <= pd.to_datetime(is_end, utc=True))]
    df_oos = df[(df.index >= pd.to_datetime(oos_start, utc=True)) & (df.index <= pd.to_datetime(oos_end, utc=True))]
    print(f"Dataset cargado: {len(df_is)} velas In-Sample | {len(df_oos)} velas Out-of-Sample.\n")

    # Step 2: Baseline Backtest on In-Sample
    print("--- [PASO 2/5] Backtest de las 5 Estrategias en In-Sample ---")
    engine = BacktestEngine(risk_profile="moderate")
    rep_gen = IndividualReportGenerator(output_dir=config.settings["reports"]["output_dir"])
    comp_gen = ComparativeReportGenerator(output_dir=config.settings["reports"]["output_dir"])
    val_gen = ValidationReportGenerator(output_dir=config.settings["reports"]["output_dir"])

    is_reports = []
    for s_id in STRATEGY_REGISTRY.keys():
        strat = get_strategy(s_id)
        res = engine.run(strat, df_is, symbol=symbol)
        rep = rep_gen.generate(res, period_type="in_sample", strategy_params=strat.parameters)
        is_reports.append(rep)
        m = rep["metrics"]
        print(f"  • {strat.name:<32} -> PF: {m['profit_factor']:.2f}, Sharpe: {m['sharpe_ratio']:.2f}, DD: {m['max_drawdown_pct']*100:.1f}%, Veredicto: {rep['verdict']}")

    comp_gen.generate(is_reports, period_type="in_sample")

    # Step 3 & 4: Out-of-Sample & Validation for all strategies
    print("\n--- [PASO 3/5] Validación en Out-of-Sample (2024) y Análisis Walk-Forward ---")
    for s_id in STRATEGY_REGISTRY.keys():
        strat = get_strategy(s_id)
        res_oos = engine.run(strat, df_oos, symbol=symbol)
        rep_oos = rep_gen.generate(res_oos, period_type="out_of_sample", strategy_params=strat.parameters)

        wf_analyzer = WalkForwardAnalyzer(risk_profile="moderate")
        wf_windows = wf_analyzer.run(STRATEGY_REGISTRY[s_id], df, symbol=symbol, max_optim_combos=10)

        # Step 5: Validation report
        val_summary = val_gen.generate(
            strategy_name=strat.name,
            in_sample_report=[r for r in is_reports if r["strategy_name"] == strat.name][0],
            out_of_sample_report=rep_oos,
            walk_forward_windows=wf_windows,
            best_params=strat.parameters
        )
        print(f"  • {strat.name:<32} -> VEREDICTO FINAL: {val_summary['final_verdict']}")

    print("\n--- [PASO 5/5] Reportes Generados Exitosamente ---")
    print(f"Directorio de reportes y gráficos: {config.settings['reports']['output_dir']}/")


def main():
    parser = argparse.ArgumentParser(description="Laboratorio de Estrategias de Trading (Strategy Lab) - CLI")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # download
    p_dl = subparsers.add_parser("download", help="Descargar datos históricos de Binance")
    p_dl.add_argument("--symbol", type=str, default=None, help="Par de trading (ej. BTC/USDT)")
    p_dl.add_argument("--timeframe", type=str, default=None, help="Timeframe (15m, 1h, 4h)")
    p_dl.add_argument("--start", type=str, default=None, help="Fecha inicio YYYY-MM-DD")
    p_dl.add_argument("--end", type=str, default=None, help="Fecha fin YYYY-MM-DD")
    p_dl.add_argument("--market", type=str, default="futures", help="Mercado (spot o futures)")
    p_dl.add_argument("--no-cache", action="store_true", help="Forzar descarga sin usar caché")

    # backtest
    p_bt = subparsers.add_parser("backtest", help="Ejecutar backtest de estrategias")
    p_bt.add_argument("--strategy", type=str, default=None, choices=list(STRATEGY_REGISTRY.keys()), help="Estrategia específica")
    p_bt.add_argument("--symbol", type=str, default=None, help="Par de trading")
    p_bt.add_argument("--timeframe", type=str, default=None, help="Timeframe")
    p_bt.add_argument("--profile", type=str, default=None, choices=["conservative", "moderate", "aggressive"], help="Perfil de riesgo")
    p_bt.add_argument("--start", type=str, default=None, help="Fecha inicio YYYY-MM-DD")
    p_bt.add_argument("--end", type=str, default=None, help="Fecha fin YYYY-MM-DD")

    # optimize
    p_opt = subparsers.add_parser("optimize", help="Optimizar parámetros de una estrategia")
    p_opt.add_argument("--strategy", type=str, required=True, choices=list(STRATEGY_REGISTRY.keys()), help="Estrategia a optimizar")
    p_opt.add_argument("--symbol", type=str, default=None, help="Par de trading")
    p_opt.add_argument("--timeframe", type=str, default=None, help="Timeframe")
    p_opt.add_argument("--method", type=str, choices=["grid", "random"], default="grid", help="Método de optimización")
    p_opt.add_argument("--max-combos", type=int, default=50, help="Número máximo de combinaciones")
    p_opt.add_argument("--profile", type=str, default="moderate", help="Perfil de riesgo")

    # walk-forward
    p_wf = subparsers.add_parser("walk-forward", help="Ejecutar análisis Walk-Forward")
    p_wf.add_argument("--strategy", type=str, required=True, choices=list(STRATEGY_REGISTRY.keys()), help="Estrategia")
    p_wf.add_argument("--symbol", type=str, default=None, help="Par de trading")
    p_wf.add_argument("--timeframe", type=str, default=None, help="Timeframe")
    p_wf.add_argument("--profile", type=str, default="moderate", help="Perfil de riesgo")

    # testnet
    p_tn = subparsers.add_parser("testnet", help="Evaluar señales y simular/ejecutar en Binance Testnet Sandbox")
    p_tn.add_argument("--strategy", type=str, default="supertrend", choices=list(STRATEGY_REGISTRY.keys()), help="Estrategia a ejecutar")
    p_tn.add_argument("--symbol", type=str, default="BTC/USDT", help="Par de trading")
    p_tn.add_argument("--timeframe", type=str, default="1h", help="Timeframe")
    p_tn.add_argument("--profile", type=str, default="moderate", help="Perfil de riesgo")
    p_tn.add_argument("--live", action="store_true", help="Desactivar modo Dry-Run y enviar orden real a Testnet (requiere API keys)")
    p_tn.add_argument("--loop", action="store_true", help="Dejar el bot corriendo continuamente en bucle en tiempo real")
    p_tn.add_argument("--interval", type=int, default=60, help="Intervalo en segundos entre chequeos de mercado (default: 60s)")

    # run-all
    p_all = subparsers.add_parser("run-all", help="Ejecutar ciclo completo end-to-end de investigación y validación")
    p_all.add_argument("--symbol", type=str, default=None, help="Par de trading")
    p_all.add_argument("--timeframe", type=str, default=None, help="Timeframe")

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Iniciar el Dashboard Web Interactivo (FastAPI + Chart.js)")
    p_dash.add_argument("--host", type=str, default="127.0.0.1", help="Host del servidor (default: 127.0.0.1)")
    p_dash.add_argument("--port", type=int, default=8000, help="Puerto del servidor (default: 8000)")

    # bot
    p_bot = subparsers.add_parser("bot", help="Iniciar el Bot Autónomo e Inteligente en Vivo (Fase 2)")
    p_bot.add_argument("--strategy", type=str, default="supertrend", choices=list(STRATEGY_REGISTRY.keys()), help="Estrategia a ejecutar")
    p_bot.add_argument("--symbol", type=str, default="BTC/USDT", help="Par de trading")
    p_bot.add_argument("--timeframe", type=str, default="1h", help="Timeframe")
    p_bot.add_argument("--profile", type=str, default="moderate", help="Perfil de riesgo")
    p_bot.add_argument("--interval", type=int, default=30, help="Intervalo en segundos entre ciclos de análisis")
    p_bot.add_argument("--live", action="store_true", help="Operar en Testnet con órdenes reales (por defecto: simulación Dry-Run)")

    args = parser.parse_args()

    if args.command == "download":
        cmd_download(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "optimize":
        cmd_optimize(args)
    elif args.command == "walk-forward":
        cmd_walk_forward(args)
    elif args.command == "testnet":
        cmd_testnet(args)
    elif args.command == "run-all":
        cmd_run_all(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "bot":
        cmd_bot(args)
    else:
        parser.print_help()


def cmd_bot(args):
    """Starts the autonomous trading bot from CLI."""
    import time
    from src.bot.bot_controller import BotController

    print("================================================================================")
    print("           INICIANDO BOT AUTÓNOMO INTELIGENTE - FASE 2                         ")
    print("================================================================================\n")
    dry_run = not args.live
    mode_str = "DRY RUN (Simulación en tiempo real sin riesgo)" if dry_run else "TESTNET CON ÓRDENES REALES"
    print(f"Modo: {mode_str}")
    print(f"Estrategia: {args.strategy} | Par: {args.symbol} [{args.timeframe}] | Perfil: {args.profile.upper()}")
    print(f"Intervalo: {args.interval}s | Presiona Ctrl+C para detener de forma segura.\n")

    controller = BotController(
        strategy_id=args.strategy,
        symbol=args.symbol,
        timeframe=args.timeframe,
        risk_profile=args.profile,
        dry_run=dry_run,
        poll_interval=args.interval
    )
    controller.start()
    try:
        while controller.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹ Deteniendo bot...")
        controller.stop()
        print("✅ Bot detenido exitosamente.")



def cmd_dashboard(args):
    """Starts the interactive web dashboard."""
    from src.dashboard.server import start_dashboard

    print("================================================================================")
    print("           INICIANDO DASHBOARD WEB INTERACTIVO - STRATEGY LAB                   ")
    print(f"           URL: http://{args.host}:{args.port}                                 ")
    print("================================================================================\n")
    start_dashboard(host=args.host, port=args.port)


def cmd_testnet(args):
    """Executes live signal evaluation and testnet simulated/live order execution."""
    from src.live.testnet_runner import TestnetRunner

    print("================================================================================")
    print("                 BINANCE TESTNET / SANDBOX RUNNER                               ")
    print("================================================================================\n")

    dry_run = not args.live
    mode_label = "DRY RUN (SIMULACIÓN SIN RIESGO)" if dry_run else "TESTNET EN VIVO (ORDEN REAL SANDBOX)"
    print(f"Modo: {mode_label}")
    print(f"Estrategia: {args.strategy} | Par: {args.symbol} | TF: {args.timeframe} | Perfil: {args.profile.upper()}\n")

    runner = TestnetRunner(
        strategy_id=args.strategy,
        symbol=args.symbol,
        timeframe=args.timeframe,
        risk_profile=args.profile,
        dry_run=dry_run
    )

    if args.loop:
        print(f"🔄 Modo Bucle Continuo Activo: Chequeando {args.symbol} cada {args.interval} segundos.")
        print("Presiona Ctrl+C en cualquier momento para detener el bot.\n")
        runner.run_loop(poll_interval=args.interval)
    else:
        result = runner.evaluate_signals()
        action_color = "🟢" if "BUY" in result["action"] else ("🔴" if "SELL" in result["action"] else "⚪")

        print(f"⏰ Última vela evaluada: {result['last_timestamp']}")
        print(f"💲 Precio de cierre actual: ${result['close_price']:,.2f}")
        print(f"{action_color} Acción generada: {result['action']}")
        print(f"🛑 Stop Loss sugerido: ${result['stop_loss']:,.2f}")
        print(f"🎯 Take Profit sugerido: ${result['take_profit']:,.2f}")

        if result["order"]:
            print(f"\n📦 Detalle de Orden: {result['order']}")
        print("\n✅ Evaluación de Testnet finalizada.")


if __name__ == "__main__":
    main()

