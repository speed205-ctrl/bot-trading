"""FastAPI server for the Trading Strategy Lab interactive dashboard."""
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.backtest.engine import BacktestEngine
from src.data.downloader import BinanceDownloader
from src.live.testnet_connector import TestnetConnector
from src.live.testnet_runner import TestnetRunner
from src.metrics import calculate_all_metrics
from src.reports.comparative_report import ComparativeReportGenerator
from src.strategies import STRATEGY_REGISTRY, get_strategy
from src.utils.config_loader import config
from src.utils.logger import setup_logger

logger = setup_logger("DashboardServer")

app = FastAPI(title="Laboratorio de Estrategias de Trading - Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class BacktestRequest(BaseModel):
    strategy: str = "supertrend"
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    start_date: str = "2024-01-01"
    end_date: str = "2024-02-01"
    profile: str = "moderate"
    initial_capital: float = 10000.0


class TestnetRequest(BaseModel):
    strategy: str = "supertrend"
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    profile: str = "moderate"


@app.get("/")
async def serve_index():
    """Serves the dashboard single page application."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"error": "Frontend index.html not found"}, status_code=404)
    return FileResponse(index_file)


@app.get("/api/strategies")
async def get_strategies_list():
    """Returns list of all available strategies and their metadata."""
    strategies = []
    strat_configs = config.strategies
    for s_id, strat_cls in STRATEGY_REGISTRY.items():
        inst = strat_cls()
        cfg = strat_configs.get(s_id, {})
        strategies.append({
            "id": s_id,
            "name": inst.name,
            "description": inst.description,
            "timeframe": inst.preferred_timeframe,
            "direction": inst.direction,
            "indicators": inst.indicators_required,
            "parameters": inst.parameters,
            "param_ranges": inst.param_ranges,
        })
    return {"strategies": strategies}


@app.get("/api/profiles")
async def get_risk_profiles():
    """Returns configured risk profiles."""
    return {"profiles": config.profiles}


@app.post("/api/backtest")
async def run_backtest(req: BacktestRequest):
    """Executes an interactive backtest and returns full performance metrics, equity curve and trade logs."""
    if req.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Estrategia '{req.strategy}' desconocida.")

    downloader = BinanceDownloader(cache_dir=config.settings["data"]["raw_dir"])
    df, meta = downloader.download_ohlcv(
        symbol=req.symbol,
        timeframe=req.timeframe,
        start_date=req.start_date,
        end_date=req.end_date,
        market_type=config.settings["exchange"]["trading_mode"],
        use_cache=True
    )

    strategy = get_strategy(req.strategy)
    engine = BacktestEngine(
        initial_capital=req.initial_capital,
        risk_profile=req.profile,
        commission_rate=config.settings["backtest"]["commission_rate"],
        slippage_pct=config.settings["backtest"]["slippage_pct"]
    )

    result = engine.run(strategy, df, symbol=req.symbol)
    metrics_report = calculate_all_metrics(result, period_type="in_sample")

    # Downsample equity curve for fast JSON transmission if needed
    eq_curve = []
    step = max(1, len(result.equity_curve) // 300)
    for idx in range(0, len(result.equity_curve), step):
        row = result.equity_curve.iloc[idx]
        eq_curve.append({
            "timestamp": str(result.equity_curve.index[idx]),
            "equity": round(float(row["equity"]), 2),
            "drawdown_pct": round(float(row["drawdown_pct"]) * 100.0, 2)
        })

    # Last point always included
    if not result.equity_curve.empty:
        last_row = result.equity_curve.iloc[-1]
        eq_curve.append({
            "timestamp": str(result.equity_curve.index[-1]),
            "equity": round(float(last_row["equity"]), 2),
            "drawdown_pct": round(float(last_row["drawdown_pct"]) * 100.0, 2)
        })

    # Trade logs (top 50 recent trades)
    trades_log = []
    for t in result.trades[-50:]:
        trades_log.append({
            "symbol": t.symbol,
            "direction": t.direction,
            "entry_time": str(t.entry_time),
            "exit_time": str(t.exit_time),
            "entry_price": round(t.entry_price, 2),
            "exit_price": round(t.exit_price, 2),
            "net_pnl": round(t.net_pnl, 2),
            "return_pct": round(t.return_pct * 100.0, 2),
            "exit_reason": t.exit_reason,
            "duration_hours": round(t.duration_hours, 1)
        })

    return {
        "strategy_id": req.strategy,
        "strategy_name": result.strategy_name,
        "risk_profile": req.profile,
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "verdict": metrics_report["verdict"],
        "metrics": metrics_report["metrics"],
        "criteria": metrics_report["criteria"],
        "warnings": metrics_report["warnings"],
        "equity_curve": eq_curve,
        "trades": trades_log,
        "total_candles": len(df)
    }


@app.get("/api/comparative")
async def get_comparative_matrix(symbol: str = "BTC/USDT", timeframe: str = "1h", days: int = 30):
    """Executes backtests on all 11 strategies and returns the comparative ranking matrix."""
    downloader = BinanceDownloader(cache_dir=config.settings["data"]["raw_dir"])
    end_dt = pd.Timestamp.now(tz="UTC")
    start_dt = end_dt - pd.Timedelta(days=days)

    df, _ = downloader.download_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        start_date=str(start_dt.date()),
        end_date=str(end_dt.date()),
        market_type=config.settings["exchange"]["trading_mode"],
        use_cache=True
    )

    engine = BacktestEngine(initial_capital=10000.0, risk_profile="moderate")
    matrix = []

    for s_id, strat_cls in STRATEGY_REGISTRY.items():
        strat = strat_cls()
        res = engine.run(strat, df, symbol=symbol)
        m_rep = calculate_all_metrics(res, period_type="in_sample")
        m = m_rep["metrics"]

        matrix.append({
            "id": s_id,
            "name": strat.name,
            "verdict": m_rep["verdict"],
            "profit_factor": round(float(m["profit_factor"]), 2),
            "sharpe_ratio": round(float(m["sharpe_ratio"]), 2),
            "max_drawdown_pct": round(float(m["max_drawdown_pct"]) * 100.0, 2),
            "total_return_pct": round(float(m["total_return_pct"]) * 100.0, 2),
            "win_rate_pct": round(float(m["win_rate_pct"]) * 100.0, 2),
            "total_trades": int(m["total_trades"]),
            "commissions": round(float(m["total_commissions"]), 2),
        })

    # Sort descending by Profit Factor
    matrix.sort(key=lambda x: x["profit_factor"], reverse=True)
    return {"strategies": matrix, "symbol": symbol, "timeframe": timeframe, "candles": len(df)}


@app.post("/api/testnet/evaluate")
async def evaluate_testnet_signal(req: TestnetRequest):
    """Evaluates live Binance Testnet signals and simulated order execution."""
    runner = TestnetRunner(
        strategy_id=req.strategy,
        symbol=req.symbol,
        timeframe=req.timeframe,
        risk_profile=req.profile,
        dry_run=True
    )
    result = runner.evaluate_signals()
    return result


def start_dashboard(host: str = "127.0.0.1", port: int = 8000):
    """Launches the Uvicorn server."""
    import uvicorn
    logger.info(f"Launching Strategy Lab Dashboard on http://{host}:{port}")
    uvicorn.run("src.dashboard.server:app", host=host, port=port, reload=False)
