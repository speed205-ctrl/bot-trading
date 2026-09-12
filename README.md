# Laboratorio de Estrategias de Trading (Strategy Lab)

Sistema automatizado de investigación, simulación cuantitativa y validación out-of-sample para evaluar estrategias de trading en criptomonedas con datos históricos reales de Binance, antes de arriesgar capital o construir un bot de ejecución en vivo.

> **Aviso Importante:** Este sistema es un laboratorio de simulación analítica. No ejecuta órdenes con dinero real ni se conecta a cuentas con fondos. Su propósito es filtrar y descartar estrategias de bajo rendimiento o sobreoptimizadas.

---

## 🏛 Arquitectura del Sistema

El proyecto está diseñado bajo una arquitectura modular desacoplada:

```
Bot trading/
├── config/                   # Configuración central en YAML
│   ├── settings.yaml         # Configuración general (exchange, timeframes, rutas)
│   ├── profiles.yaml         # Perfiles de riesgo (Conservador, Moderado, Agresivo)
│   └── strategies.yaml       # Parámetros y espacios de optimización de estrategias
├── data/
│   ├── raw/                  # Datos crudos descargados de Binance (CSV/Parquet)
│   └── processed/            # Datos limpios, normalizados y validados
├── results/
│   ├── backtests/            # Resultados de ejecuciones de backtest
│   ├── optimizations/        # Resultados de Grid / Random Search
│   └── reports/              # Reportes en Markdown, JSON y gráficos PNG
├── src/
│   ├── data/                 # Descarga paginada Binance, caché local y validación
│   ├── strategies/           # BaseStrategy, biblioteca de indicadores y las 5 estrategias
│   ├── backtest/             # Motor vela a vela, simulador de órdenes y costos
│   ├── optimizer/            # Grid Search, Random Search y Walk-Forward rodante
│   ├── metrics/              # Métricas de rendimiento, riesgo y estadísticas operativas
│   ├── reports/              # Reportes individuales, comparativos y generador de gráficos
│   └── utils/                # Logging centralizado, cargador de configuración y helpers
├── tests/                    # Suite completa de pruebas unitarias (Pytest)
├── main.py                   # Interfaz de línea de comandos (CLI)
└── requirements.txt          # Dependencias de Python
```

---

## 🚀 Instalación y Requisitos

### Requisitos Previos
- Python 3.10 o superior (compatible con Windows, Linux y macOS).
- Git instalado.
- Conexión a Internet para descargar datos públicos de Binance (no requiere claves API).

### Pasos de Instalación
1. Clonar el repositorio:
   ```bash
   git clone https://github.com/speed205-ctrl/bot-trading.git
   cd bot-trading
   ```
2. Crear y activar el entorno virtual:
   - **En Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **En Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

---

## 📊 Dashboard Web Interactivo

El proyecto incluye un dashboard interactivo web de grado profesional construido con **FastAPI** y **Chart.js** con diseño dark-mode y glassmorphism:

```bash
python main.py dashboard
```
Accede desde tu navegador a: **`http://localhost:8000`**

El dashboard cuenta con 3 módulos interactivos:
1. **Matriz Comparativa de Rendimiento:** Ranking en vivo de las 11 estrategias con Profit Factor, Sharpe, Max Drawdown, Retorno y Veredicto cuantitativo.
2. **Backtest Studio:** Ejecuta simulaciones instantáneas con curvas de equity interactivas, métricas clave (Win Rate, Profit Factor, Sharpe, Sortino, Calmar, VaR 95%) y registro de operaciones.
3. **Binance Testnet Sandbox:** Escaneo en tiempo real de velas y cálculo de señales de compra/venta con Stop Loss y Take Profit sugeridos, sin arriesgar capital real.

---

## 💻 Guía de Uso de la Interfaz CLI (`main.py`)

El sistema cuenta con una consola interactiva unificada con comandos directos:

### 1. Descarga y Validación de Datos Históricos
Descarga velas OHLCV de Binance (spot o futuros USDT-M) con paginación automática, manejo de reintentos, validación de integridad y caché local:
```bash
# Descarga por defecto (BTC/USDT 1h futuros entre 2021 y 2024)
python main.py download

# Descarga personalizada
python main.py download --symbol ETH/USDT --timeframe 15m --start 2023-01-01 --end 2024-12-31 --market futures
```

### 2. Ejecución de Backtest
Ejecuta la simulación sobre datos históricos vela a vela, aplicando comisiones y slippage:
```bash
# Probar todas las estrategias con perfil moderado
python main.py backtest

# Probar una estrategia específica con perfil conservador
python main.py backtest --strategy trend_pullback_atr --profile conservative --start 2021-01-01 --end 2023-12-31
```

### 3. Optimización de Parámetros (In-Sample)
Explora combinaciones de parámetros mediante Grid Search o Random Search sobre el periodo de entrenamiento (2021-2023):
```bash
# Grid Search
python main.py optimize --strategy trend_pullback_atr --method grid --max-combos 50

# Random Search
python main.py optimize --strategy ema_cross_adx --method random --max-combos 40
```

### 4. Análisis Walk-Forward (Ventanas Rodantes)
Ejecuta validación cruzada con ventanas móviles (6 meses entrenamiento / 2 meses prueba / 2 meses desplazamiento):
```bash
python main.py walk-forward --strategy trend_pullback_atr
```

### 5. Evaluación y Simulación en Binance Testnet (Sandbox)
Ejecuta la estrategia en tiempo real sobre datos recientes de Binance Testnet en modo Sandbox (Dry-Run seguro sin riesgo de fondos o con claves de Testnet):
```bash
# Simulación Dry-Run con Supertrend en BTC/USDT 1h
python main.py testnet --strategy supertrend --symbol BTC/USDT

# Evaluación con Donchian Breakout
python main.py testnet --strategy donchian_breakout --symbol ETH/USDT --timeframe 15m

# Ejecución real en Sandbox Testnet (requiere claves en testnet_config.yaml o variables de entorno)
python main.py testnet --strategy supertrend --live
```

### 6. Ciclo Completo de Laboratorio (End-to-End)
Ejecuta en un solo comando el ciclo completo de investigación: descarga, backtest baseline, optimización in-sample, validación out-of-sample, walk-forward y generación de todos los reportes y gráficos:
```bash
python main.py run-all
```

### 7. Bot de Trading Autónomo e Inteligente en Tiempo Real (Fase 2)
Ejecuta el bot en vivo con persistencia SQLite, circuit breakers de protección diaria y trailing stop:
```bash
# Modo Simulación en Vivo (Dry-Run seguro con datos reales de Binance)
python main.py bot --strategy supertrend --symbol BTC/USDT --profile moderate --interval 30

# Modo Binance Testnet Real (con claves API en testnet_config.yaml)
python main.py bot --strategy supertrend --symbol BTC/USDT --live
```

---

## 📈 Las 11 Estrategias Cuantitativas Implementadas

| ID | Estrategia | Indicadores | Lógica de Entrada | Lógica de Salida |
| :--- | :--- | :--- | :--- | :--- |
| `trend_pullback_atr` | **Trend Pullback ATR** | EMA 200, RSI 14, ATR 14 | Precio > EMA 200 y RSI cruza de vuelta al alza tras sobreventa (< 30) | SL/TP dinámicos por ATR o sobrecompra en RSI (> 70) |
| `ema_cross_adx` | **Cruce EMAs con ADX** | EMA rápida, EMA lenta, ADX 14, EMA 200, ATR 14 | Cruce alcista EMA rápida sobre lenta, ADX > umbral y Precio > EMA 200 | Cruce bajista de EMAs o SL/TP por ATR |
| `bollinger_breakout` | **Bollinger Breakout** | Bandas Bollinger, SMA Volumen, ATR 14 | Cierre supera banda superior tras compresión de ancho de banda y con volumen anormal | Caída bajo la banda media o SL/TP dinámico |
| `rsi_mean_reversion` | **Reversión Media RSI** | RSI, EMA 200, ATR 14 | Precio > EMA 200 y rebote desde sobreventa extrema | Retorno de RSI a zona neutral (50) o SL/TP por ATR |
| `macd_momentum` | **Momentum MACD Volumen** | MACD, Señal MACD, EMA 200, SMA Volumen, ATR 14 | Cruce alcista de MACD sobre línea de señal, Precio > EMA 200 y volumen > promedio | Cruce bajista MACD o SL/TP por ATR |
| `supertrend` | **Supertrend + Volumen** | Supertrend (10, 3.0), SMA Volumen, ATR 14 | Giro de Supertrend a alcista confirmado por volumen superior al promedio | Giro de Supertrend a bajista o SL dinámico |
| `donchian_breakout` | **Donchian Breakout (Turtle)** | Donchian 20/10, EMA 200, ATR 14 | Ruptura de máximos de 20 periodos sobre EMA 200 | Ruptura de mínimos de 10 periodos o SL por ATR |
| `keltner_squeeze` | **Keltner Squeeze Breakout** | Bollinger Bands, Keltner Channels, MACD Hist | Disparo de compresión de volatilidad (Bollinger fuera de Keltner) con momentum alcista | Caída bajo línea central Keltner o SL por ATR |
| `stoch_rsi` | **Doble Momentum Estocástico + RSI** | RSI 14, Estocástico (14, 3), EMA 200, ATR 14 | Sobreventa sincrónica en RSI y cruce alcista de Estocástico en tendencia macro | Estocástico > 75 o SL/TP por ATR |
| `vwap_reversion` | **Reversión Media VWAP** | Rolling VWAP 24h, Bandas de Desviación, EMA 200 | Rechazo y cierre por encima de la banda inferior de VWAP en tendencia alcista | Retorno al VWAP medio o banda superior |
| `triple_ema_ribbon` | **Cinta de Medias Triples** | EMA 8, EMA 21, EMA 55, ATR 14 | Alineación 8 > 21 > 55 y retroceso con rebote en la EMA 21 | EMA 8 cruza bajo EMA 21 o SL/TP por ATR |


---

## 🛡 Perfiles de Riesgo y Gestión de Capital

El dimensionamiento de posición utiliza la fórmula estricta basada en volatilidad:
$$\text{Tamaño Posición (unidades)} = \frac{\text{Capital} \times \text{Riesgo \%}}{\text{Distancia Stop Loss en Precio}}$$
Donde la distancia del stop loss equivale a: $\text{Multiplicador ATR} \times \text{Valor ATR}$.

| Parámetro | Perfil Conservador | Perfil Moderado | Perfil Agresivo |
| :--- | :---: | :---: | :---: |
| **Riesgo por operación** | 1.0% | 2.0% | 4.0% |
| **Apalancamiento máximo** | 5x | 10x | 20x |
| **Tipo de margen** | Aislado | Aislado | Aislado |
| **Máx. Posiciones simultáneas** | 1 | 1 | 2 |
| **Drawdown diario máximo** | 3.0% | 5.0% | 8.0% |
| **Drawdown total máximo** | 15.0% | 20.0% | 30.0% |

---

## 🎯 Criterios Cuantitativos de Aprobación (Sección 8)

Para que una estrategia reciba el veredicto **APROBADA PARA FASE 2 (BOT)** debe superar todos los filtros:

### Criterios In-Sample (2021-2023)
- **Profit Factor:** > 1.3
- **Máximo Drawdown:** < 20%
- **Win Rate:** > 40%
- **Operaciones Totales:** > 100
- **Ratio de Sharpe:** > 1.0
- **Retorno Neto:** > 0% después de comisiones y slippage

### Criterios Out-of-Sample (2024)
- **Profit Factor:** > 1.1
- **Máximo Drawdown:** < 25%
- **Win Rate:** > 35%
- **Operaciones Totales:** > 30
- **Ratio de Sharpe:** > 0.8

### Criterios de Degradación y Robustez (Sobreajuste)
- La degradación de Profit Factor no debe superar el 40%.
- La degradación del Ratio de Sharpe no debe superar el 40%.
- El Drawdown en Out-of-Sample no debe superar en más del 25% al Drawdown In-Sample.
- Debe mantener Profit Factor > 1.0 en al menos 4 de 6 ventanas rodantes de Walk-Forward.
- No debe registrar pérdidas totales de cuenta en ninguna ventana.

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una cobertura integral de pruebas unitarias sobre todos los componentes:
```bash
pytest tests/ -v
```

Módulos testeados:
1. `tests/test_data_module.py`: Descarga, caché, detección y rellenado de gaps, validación de integridad.
2. `tests/test_strategies.py`: Cálculo matemático de indicadores y generación de señales para las 5 estrategias.
3. `tests/test_backtest_engine.py`: Motor vela a vela, simulador de órdenes, comisiones y margin limits.
4. `tests/test_metrics.py`: Fórmulas financieras (Sharpe, Sortino, Calmar, VaR) y generadores de reportes.
5. `tests/test_optimizer.py`: Grid Search, Random Search, Walk-Forward y detección de sobreoptimización.

---

## 🔄 Transición a Fase 2 (Bot de Ejecución Real)

Una vez que el laboratorio valida una estrategia con veredicto aprobatorio:
- **Se reutiliza:** El código de la estrategia validada (`src/strategies/`), los parámetros optimizados, los indicadores y la estructura de datos.
- **Se construye:** El motor de ejecución de órdenes en tiempo real con claves autenticadas de Binance API, gestión de balances y margin en vivo, y dashboard de supervisión.
- **Se sustituye:** La simulación de órdenes históricas se reemplaza por órdenes de mercado/límite en vivo.

---

## 📄 Licencia
Este proyecto es código abierto bajo la licencia MIT.