SPEC: Laboratorio de Estrategias de Trading
Documento de Especificación para Desarrollo
1. OBJETIVO DEL SISTEMA
Crear un sistema de pruebas automatizado para evaluar estrategias de trading en criptomonedas antes de construir un bot de ejecución real. El sistema debe permitir probar múltiples estrategias contra datos históricos de Binance, comparar sus resultados y seleccionar únicamente las que cumplan criterios mínimos de rendimiento.
El sistema NO ejecuta operaciones reales. Solo simula y analiza.
2. ALCANCE
Incluye
Descarga de datos históricos desde Binance
Implementación de 5 estrategias de trading
Motor de backtesting
Calculadora de métricas de rendimiento
Optimizador de parámetros
Generador de reportes comparativos
Validación out-of-sample
Configuración de perfiles de riesgo
No incluye
Ejecución de operaciones reales
Conexión a cuentas de exchange con fondos
Interfaces de usuario complejas
Sistemas de pago o suscripción
WhatsApp Business API
3. ARQUITECTURA DEL SISTEMA
El sistema se divide en 6 módulos principales que funcionan de forma independiente pero conectados entre sí.
Módulo 1: Gestor de Datos
Responsable de obtener, almacenar y servir los datos de mercado.
Módulo 2: Framework de Estrategias
Define la estructura base que todas las estrategias deben seguir.
Módulo 3: Motor de Backtesting
Simula la ejecución de estrategias sobre datos históricos.
Módulo 4: Optimizador de Parámetros
Prueba combinaciones de parámetros para cada estrategia.
Módulo 5: Calculadora de Métricas
Calcula indicadores de rendimiento y riesgo.
Módulo 6: Generador de Reportes
Produce reportes comparativos y de validación.
4. ESPECIFICACIÓN DE MÓDULOS
4.1 Módulo de Datos
Responsabilidad: Descargar, cachear y servir datos históricos de mercado.
Comportamiento:
Conectar a la API pública de Binance sin necesidad de claves de autenticación
Descargar velas OHLCV para pares específicos
Soportar múltiples timeframes: 15m, 1h, 4h
Almacenar datos en archivos locales para evitar descargas repetidas
Verificar integridad de datos descargados
Detectar y rellenar gaps en los datos si existen
Permitir especificar rango de fechas inicio y fin
Datos de entrada:
Símbolo del par (ejemplo: BTC/USDT)
Timeframe
Fecha inicio
Fecha fin
Modo de trading (spot o futures)
Datos de salida:
DataFrame con columnas: fecha, apertura, máximo, mínimo, cierre, volumen
Metadata: número de velas, rango temporal, gaps detectados
Reglas:
Si los datos ya existen en caché, no descargar de nuevo
Si la descarga falla, reintentar hasta 3 veces
Validar que no existan velas con valores nulos o negativos
4.2 Framework de Estrategias
Responsabilidad: Definir la interfaz común que todas las estrategias deben implementar.
Comportamiento:
Toda estrategia debe heredar de una clase base
Toda estrategia debe implementar métodos obligatorios de cálculo de indicadores, generación de señales de entrada y generación de señales de salida
Toda estrategia debe declarar sus parámetros optimizables
Toda estrategia debe definir su timeframe preferido
Toda estrategia debe indicar si opera solo long, solo short, o ambos
Estructura de una estrategia:
Nombre único identificador
Descripción textual
Lista de indicadores requeridos
Parámetros con sus rangos de optimización
Reglas de entrada en formato lógico
Reglas de salida en formato lógico
Gestión de stop loss y take profit
Filtro de tendencia opcional
Reglas:
Una estrategia no puede modificar datos de entrada
Una estrategia no puede ejecutar órdenes directamente
Una estrategia solo produce señales
Las señales deben ser binarias: comprar, vender, o mantener
4.3 Motor de Backtesting
Responsabilidad: Simular la ejecución de una estrategia sobre datos históricos.
Comportamiento:
Recibir una estrategia y un dataset
Iterar vela por vela aplicando las reglas de la estrategia
Simular apertura y cierre de posiciones
Calcular comisiones y slippage en cada operación
Registrar cada operación con todos sus detalles
Mantener un registro del equity curve
Aplicar los perfiles de riesgo configurados
Datos de entrada:
Estrategia a probar
Dataset histórico
Capital inicial
Perfil de riesgo
Configuración de comisiones
Configuración de apalancamiento
Datos de salida:
Lista de operaciones realizadas
Equity curve
Métricas de rendimiento
Logs de ejecución
Reglas:
No permitir operaciones con capital insuficiente
Aplicar comisión en cada entrada y salida
Aplicar slippage configurable
Respetar el apalancamiento máximo del perfil
Respetar el margen aislado
Una sola posición abierta por par al mismo tiempo
Si el capital llega a cero, detener el backtest
Simulación de ejecución:
Las órdenes de entrada se ejecutan al precio de apertura de la siguiente vela después de la señal
Las órdenes de salida se ejecutan al precio de activación del stop loss, take profit, o señal de salida
El slippage se aplica como un porcentaje adicional al precio de ejecución
4.4 Optimizador de Parámetros
Responsabilidad: Encontrar la mejor combinación de parámetros para cada estrategia.
Comportamiento:
Recibir una estrategia con sus rangos de parámetros
Generar combinaciones de parámetros usando grid search o random search
Ejecutar backtest para cada combinación
Almacenar resultados de cada combinación
Ordenar resultados por métrica objetivo
Detectar sobreoptimización comparando in-sample vs out-of-sample
Datos de entrada:
Estrategia a optimizar
Dataset in-sample
Dataset out-of-sample
Métrica objetivo a maximizar
Método de búsqueda
Número máximo de combinaciones
Datos de salida:
Tabla de combinaciones con sus resultados
Mejor combinación encontrada
Comparativa in-sample vs out-of-sample
Advertencias de sobreoptimización si aplica
Reglas:
Nunca optimizar usando datos out-of-sample
Si una combinación produce menos de 30 operaciones, descartarla
Si la degradación out-of-sample supera el 40%, marcar como sobreoptimizada
Limitar el número máximo de combinaciones para evitar tiempos excesivos
4.5 Calculadora de Métricas
Responsabilidad: Calcular indicadores de rendimiento y riesgo a partir de los resultados del backtest.
Métricas a calcular:
Rendimiento:
Retorno total en porcentaje
Retorno anualizado
Profit factor
Ratio de Sharpe
Ratio de Sortino
Ratio de Calmar
Promedio de ganancia por operación
Promedio de pérdida por operación
Ratio riesgo beneficio promedio
Riesgo:
Máximo drawdown en porcentaje
Máximo drawdown en valor absoluto
Duración del máximo drawdown
Volatilidad de retornos
Value at Risk al 95%
Número de pérdidas consecutivas máximas
Operaciones:
Número total de operaciones
Porcentaje de operaciones ganadoras
Porcentaje de operaciones perdedoras
Duración promedio de operaciones
Duración máxima de una operación
Frecuencia de operaciones por semana
Costos:
Total de comisiones pagadas
Total de slippage estimado
Impacto de costos en el retorno
Reglas:
Si el número de operaciones es menor a 30, marcar como muestra insuficiente
Si el profit factor es menor a 1, marcar como estrategia perdedora
Si el máximo drawdown supera el 30%, marcar como alto riesgo
4.6 Generador de Reportes
Responsabilidad: Producir reportes legibles y comparativos de los resultados.
Tipos de reporte:
Reporte individual de estrategia:
Nombre de la estrategia
Parámetros utilizados
Métricas completas
Gráfico del equity curve
Gráfico del drawdown
Lista de operaciones
Veredicto: pasa o no pasa
Reporte comparativo:
Tabla con todas las estrategias y sus métricas clave
Ranking por profit factor
Ranking por drawdown
Ranking por Sharpe
Estrategias que pasan los criterios
Estrategias descartadas
Reporte de validación:
Comparativa in-sample vs out-of-sample
Análisis de walk-forward
Detección de sobreoptimización
Recomendaciones finales
Formato de salida:
Texto plano para consola
Markdown para documentación
JSON para procesamiento posterior
Imágenes PNG para gráficos si es posible
5. ESTRATEGIAS A IMPLEMENTAR
5.1 Estrategia: Trend Pullback ATR
Tipo: Seguimiento de tendencia con entrada en retroceso
Dirección: Solo Long
Timeframe: 1 hora
Indicadores requeridos:
Media móvil exponencial de 200 periodos
RSI de 14 periodos
ATR de 14 periodos
Lógica de entrada:
El precio de cierre debe estar por encima de la EMA de 200
El RSI debe haber estado por debajo del umbral de sobreventa en la vela anterior
El RSI debe cruzar por encima del umbral de sobreventa en la vela actual
Lógica de salida:
Stop loss calculado como múltiplo del ATR por debajo del precio de entrada
Take profit calculado como múltiplo del ATR por encima del precio de entrada
Salida alternativa si el RSI supera el nivel de sobrecompra
Parámetros optimizables:
Umbral de sobreventa del RSI: rango de 25 a 40
Multiplicador de ATR para stop loss: rango de 1.5 a 3.0
Multiplicador de ATR para take profit: rango de 2.0 a 5.0
Nivel de sobrecompra para salida: rango de 65 a 80
5.2 Estrategia: Cruce de EMAs con Filtro ADX
Tipo: Momentum con filtro de fuerza de tendencia
Dirección: Solo Long
Timeframe: 1 hora
Indicadores requeridos:
EMA rápida
EMA lenta
ADX de 14 periodos
EMA de 200 periodos como filtro de tendencia
Lógica de entrada:
La EMA rápida cruza por encima de la EMA lenta
El ADX está por encima del umbral de fuerza de tendencia
El precio de cierre está por encima de la EMA de 200
Lógica de salida:
La EMA rápida cruza por debajo de la EMA lenta
Stop loss basado en ATR
Take profit basado en ATR
Parámetros optimizables:
Periodo de EMA rápida: rango de 7 a 15
Periodo de EMA lenta: rango de 18 a 30
Umbral de ADX: rango de 20 a 35
Multiplicador de ATR para stop loss: rango de 1.5 a 3.0
Multiplicador de ATR para take profit: rango de 2.0 a 5.0
5.3 Estrategia: Breakout de Bandas de Bollinger
Tipo: Breakout de volatilidad
Dirección: Solo Long
Timeframe: 1 hora
Indicadores requeridos:
Bandas de Bollinger con periodo y desviación estándar configurables
Media móvil simple de volumen
Lógica de entrada:
El precio de cierre supera la banda superior de Bollinger
Las bandas estaban comprimidas antes del breakout
El volumen de la vela actual es mayor que la media de volumen multiplicada por un factor
Lógica de salida:
Stop loss en la banda media de Bollinger
Take profit calculado como múltiplo del ancho de banda
Stop loss alternativo basado en ATR
Parámetros optimizables:
Periodo de Bandas de Bollinger: rango de 14 a 30
Desviación estándar: rango de 1.5 a 3.0
Factor de volumen: rango de 1.2 a 2.5
Umbral de compresión de bandas: rango de 0.5 a 2.0
Multiplicador de ancho de banda para take profit: rango de 1.5 a 3.0
5.4 Estrategia: Reversión a la Media con RSI
Tipo: Reversión a la media en tendencia
Dirección: Solo Long
Timeframe: 1 hora
Indicadores requeridos:
RSI con periodo configurable
EMA de 200 periodos como filtro de tendencia
Lógica de entrada:
El precio de cierre está por encima de la EMA de 200
El RSI cae por debajo del nivel de sobreventa
El RSI cruza de vuelta por encima del nivel de sobreventa
Lógica de salida:
El RSI supera el nivel de salida
Stop loss basado en ATR
Take profit basado en ATR
Parámetros optimizables:
Periodo de RSI: rango de 7 a 21
Nivel de sobreventa: rango de 20 a 35
Nivel de salida: rango de 45 a 60
Multiplicador de ATR para stop loss: rango de 1.5 a 3.0
Multiplicador de ATR para take profit: rango de 2.0 a 5.0
5.5 Estrategia: Momentum MACD con Volumen
Tipo: Momentum con confirmación de volumen
Dirección: Solo Long
Timeframe: 1 hora
Indicadores requeridos:
MACD con periodos configurables
Línea de señal del MACD
EMA de 200 periodos como filtro de tendencia
Media móvil simple de volumen
Lógica de entrada:
La línea MACD cruza por encima de la línea de señal
El precio de cierre está por encima de la EMA de 200
El volumen de la vela actual es mayor que la media de volumen multiplicada por un factor
Lógica de salida:
La línea MACD cruza por debajo de la línea de señal
Stop loss basado en ATR
Take profit basado en ATR
Parámetros optimizables:
Periodo rápido del MACD: rango de 8 a 16
Periodo lento del MACD: rango de 21 a 31
Periodo de señal del MACD: rango de 7 a 11
Factor de volumen: rango de 1.0 a 2.0
Multiplicador de ATR para stop loss: rango de 1.5 a 3.0
Multiplicador de ATR para take profit: rango de 2.0 a 5.0
6. PERFILES DE RIESGO
El sistema debe soportar tres perfiles de riesgo configurables que afectan el tamaño de posición y el apalancamiento.
Perfil Conservador
Riesgo por operación: 1% del capital
Apalancamiento máximo: 5x
Margen: aislado
Máximo de posiciones simultáneas: 1
Drawdown diario máximo: 3%
Drawdown total máximo: 15%
Perfil Moderado
Riesgo por operación: 2% del capital
Apalancamiento máximo: 10x
Margen: aislado
Máximo de posiciones simultáneas: 1
Drawdown diario máximo: 5%
Drawdown total máximo: 20%
Perfil Agresivo
Riesgo por operación: 4% del capital
Apalancamiento máximo: 20x
Margen: aislado
Máximo de posiciones simultáneas: 2
Drawdown diario máximo: 8%
Drawdown total máximo: 30%
Fórmula de tamaño de posición
El tamaño de posición se calcula como el capital multiplicado por el porcentaje de riesgo, dividido por la distancia del stop loss en precio. La distancia del stop loss se calcula como el multiplicador de ATR multiplicado por el valor del ATR.
7. METODOLOGÍA DE PRUEBAS
7.1 División de datos
In-Sample (entrenamiento):
Periodo: 1 de enero de 2021 a 31 de diciembre de 2023
Uso: optimización de parámetros
No se usa para validación final
Out-of-Sample (validación):
Periodo: 1 de enero de 2024 a 31 de diciembre de 2024
Uso: validación de estrategias ya optimizadas
No se usa para optimización
7.2 Walk-Forward Analysis
Dividir el periodo total en ventanas rodantes.
Configuración:
Ventana de entrenamiento: 6 meses
Ventana de prueba: 2 meses
Desplazamiento: 2 meses
Proceso:
Optimizar parámetros en la ventana de entrenamiento
Probar en la ventana de prueba
Desplazar las ventanas
Repetir hasta cubrir todo el periodo
Consolidar resultados
7.3 Prueba de robustez
Para cada estrategia validada, ejecutar pruebas adicionales:
Cambiar el timeframe a 15 minutos y 4 horas
Cambiar el par a ETH/USDT
Agregar comisión adicional del 0.02%
Agregar slippage adicional del 0.05%
Verificar que los resultados no se degraden más del 30%
8. CRITERIOS DE APROBACIÓN
Una estrategia se considera válida para pasar a la fase de bot si cumple TODOS los siguientes criterios.
Criterios In-Sample
Profit factor mayor a 1.3
Máximo drawdown menor a 20%
Porcentaje de operaciones ganadoras mayor a 40%
Número total de operaciones mayor a 100
Ratio de Sharpe mayor a 1.0
Retorno total mayor a 0 después de comisiones
Criterios Out-of-Sample
Profit factor mayor a 1.1
Máximo drawdown menor a 25%
Porcentaje de operaciones ganadoras mayor a 35%
Número total de operaciones mayor a 30
Ratio de Sharpe mayor a 0.8
Criterios de degradación
La degradación del profit factor entre in-sample y out-of-sample no debe superar el 40%
La degradación del ratio de Sharpe no debe superar el 40%
El drawdown out-of-sample no debe superar en más del 25% al drawdown in-sample
Criterios de robustez
La estrategia debe mantener profit factor mayor a 1.0 en al menos 4 de 6 ventanas de walk-forward
La estrategia no debe producir pérdidas totales en ninguna ventana de walk-forward
9. CONFIGURACIÓN DEL SISTEMA
El sistema debe leer toda su configuración desde un archivo central.
Parámetros configurables
Exchange:
Nombre del exchange
Modo de trading: spot o futures
Pares a analizar
Timeframes disponibles
Backtesting:
Capital inicial
Comisión por operación
Slippage estimado
Apalancamiento por defecto
Tipo de margen
Datos:
Ruta de almacenamiento de datos
Rango de fechas por defecto
Timeframe principal
Optimización:
Método de búsqueda: grid o random
Número máximo de combinaciones
Métrica objetivo
Número de trabajos en paralelo
Reportes:
Formato de salida
Ruta de almacenamiento
Nivel de detalle
10. FLUJO DE TRABAJO
Paso 1: Descarga de datos
El usuario especifica el par, el timeframe y el rango de fechas. El sistema descarga los datos de Binance y los almacena localmente.
Paso 2: Selección de estrategias
El usuario selecciona una o varias estrategias para probar. El sistema valida que las estrategias estén correctamente implementadas.
Paso 3: Backtest inicial
El sistema ejecuta un backtest rápido con parámetros por defecto para cada estrategia seleccionada. Genera un reporte preliminar.
Paso 4: Optimización
El usuario selecciona las estrategias que mostraron potencial. El sistema ejecuta la optimización de parámetros usando el dataset in-sample.
Paso 5: Validación
El sistema ejecuta las estrategias optimizadas sobre el dataset out-of-sample. Compara resultados con el in-sample.
Paso 6: Walk-Forward
El sistema ejecuta el análisis walk-forward para las estrategias que pasaron la validación.
Paso 7: Reporte final
El sistema genera un reporte comparativo final con todas las estrategias, indicando cuáles pasan los criterios y cuáles no.
Paso 8: Selección
El usuario selecciona las estrategias validadas para pasar a la fase de construcción del bot.

strategy-lab/
│
├── config/
│   ├── settings.yaml
│   ├── profiles.yaml
│   └── strategies.yaml
│
├── src/
│   ├── data/
│   │   ├── downloader
│   │   ├── cache_manager
│   │   └── data_validator
│   │
│   ├── strategies/
│   │   ├── base_strategy
│   │   ├── trend_pullback_atr
│   │   ├── ema_cross_adx
│   │   ├── bollinger_breakout
│   │   ├── rsi_mean_reversion
│   │   └── macd_momentum
│   │
│   ├── backtest/
│   │   ├── engine
│   │   ├── position_manager
│   │   ├── order_simulator
│   │   └── cost_calculator
│   │
│   ├── optimizer/
│   │   ├── grid_search
│   │   ├── random_search
│   │   └── walk_forward
│   │
│   ├── metrics/
│   │   ├── performance_metrics
│   │   ├── risk_metrics
│   │   └── trade_statistics
│   │
│   ├── reports/
│   │   ├── individual_report
│   │   ├── comparative_report
│   │   └── validation_report
│   │
│   └── utils/
│       ├── logger
│       ├── config_loader
│       └── helpers
│
├── data/
│   ├── raw/
│   └── processed/
│
├── results/
│   ├── backtests/
│   ├── optimizations/
│   └── reports/
│
├── tests/
│   ├── test_data_module
│   ├── test_strategies
│   ├── test_backtest_engine
│   └── test_metrics
│
└── README.md

12. REQUISITOS NO FUNCIONALES
Rendimiento
El backtest de una estrategia con 3 años de datos en 1 hora debe completar en menos de 30 segundos
La optimización de 100 combinaciones de parámetros debe completar en menos de 30 minutos
El sistema debe soportar ejecución paralela de backtests
Confiabilidad
El sistema debe manejar errores de red al descargar datos
El sistema debe validar datos antes de procesarlos
El sistema debe guardar resultados parciales en caso de interrupción
Usabilidad
El sistema debe poder ejecutarse desde línea de comandos
El sistema debe mostrar progreso durante operaciones largas
El sistema debe generar reportes legibles sin necesidad de herramientas externas
Portabilidad
El sistema debe funcionar en Windows, macOS y Linux
El sistema no debe depender de servicios externos de pago
El sistema debe usar solo dependencias gratuitas y open source
Mantenibilidad
El código debe estar modularizado
Cada módulo debe tener tests unitarios
La documentación debe incluir ejemplos de uso
13. DEPENDENCIAS
Obligatorias
Lenguaje de programación: Python 3.10 o superior
Manipulación de datos: pandas, numpy
Indicadores técnicos: ta-lib o pandas-ta
Conexión a exchange: ccxt
Visualización: matplotlib o plotly
Opcionales
Ejecución paralela: multiprocessing o joblib
Reportes avanzados: jinja2 para templates HTML
Optimización avanzada: optuna
Prohibidas
Cualquier librería que requiera suscripción de pago
Cualquier servicio externo que requiera API key de pago
Cualquier dependencia que no sea open source
14. ENTREGABLES
Entrega 1: Sistema de datos
Módulo de descarga funcional
Módulo de caché funcional
Módulo de validación funcional
Tests unitarios
Entrega 2: Framework de estrategias
Clase base implementada
Una estrategia de ejemplo implementada
Documentación de la interfaz
Entrega 3: Motor de backtesting
Motor funcional con simulación de órdenes
Calculadora de comisiones y slippage
Registro de operaciones
Tests unitarios
Entrega 4: Las 5 estrategias
Todas las estrategias implementadas
Tests unitarios para cada una
Documentación de parámetros
Entrega 5: Optimizador y walk-forward
Optimizador funcional
Walk-forward funcional
Detección de sobreoptimización
Entrega 6: Métricas y reportes
Calculadora de métricas completa
Generador de reportes individuales
Generador de reporte comparativo
Generador de reporte de validación
Entrega 7: Documentación
README con instrucciones de instalación
Guía de uso
Ejemplos de configuración
Explicación de métricas
15. CRITERIOS DE ACEPTACIÓN DEL SISTEMA
El sistema se considera completo cuando:
Puede descargar datos de Binance sin errores
Puede ejecutar backtests de las 5 estrategias
Puede optimizar parámetros y detectar sobreoptimización
Puede ejecutar walk-forward analysis
Genera reportes comparativos claros
Todos los tests unitarios pasan
La documentación es suficiente para usar el sistema sin ayuda
El sistema funciona en al menos dos sistemas operativos diferentes
No requiere ningún servicio de pago para funcionar
Completa un ciclo completo de prueba en menos de 1 hora
16. TRANSICIÓN A FASE 2
Cuando el laboratorio esté funcionando y se hayan seleccionado estrategias validadas, la transición a la fase de bot requiere:
Lo que se reutiliza
El código de las estrategias validadas
Los parámetros optimizados
La lógica de indicadores
La estructura de datos
Lo que se construye nuevo
Motor de ejecución de órdenes reales
Conexión autenticada a Binance
Gestión de riesgo en tiempo real
Sistema de alertas
Dashboard de monitoreo
Modo dry-run para pruebas finales
Modo live para operación real
Lo que se modifica
El motor de backtesting se reemplaza por el motor de ejecución
La simulación de órdenes se reemplaza por órdenes reales
Los datos históricos se reemplazan por datos en tiempo real
17. NOTAS FINALES
Este sistema es un laboratorio de investigación. No debe ejecutar operaciones reales bajo ninguna circunstancia durante la fase de pruebas.
El objetivo es eliminar estrategias malas antes de arriesgar capital. Si ninguna estrategia pasa los criterios, el sistema habrá cumplido su función al evitar pérdidas.
La prioridad es la robustez del proceso de validación, no la velocidad de desarrollo. Es preferible tener un sistema lento pero confiable que un sistema rápido pero que produzca resultados falsos.