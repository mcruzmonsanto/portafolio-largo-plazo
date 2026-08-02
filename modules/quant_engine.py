import yfinance as yf
import pandas as pd
import numpy as np
import concurrent.futures
from modules.data_ingestion import DataProvider
from modules.scoring_engine import CompositeScorer
from modules.data_quality import DataQualityMonitor
from modules.montecarlo import MonteCarloEngine
import warnings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def fetch_quant_data(tickers):
    """
    Descarga el histórico de precios de 1 año y calcula indicadores técnicos 
    para una lista de tickers usando yfinance.
    Incluye el SPY para calcular el Beta.
    """
    if not tickers:
        return pd.DataFrame()
        
    tickers_with_spy = list(set(tickers + ['SPY']))
    try:
        # Descargamos 2 años de datos diarios para Monte Carlo
        data = yf.download(tickers_with_spy, period="2y", interval="1d", group_by='ticker', auto_adjust=True, progress=False)
    except Exception as e:
        print(f"Error descargando datos: {e}")
        return pd.DataFrame()

    results = []
    
    # Calcular retornos del benchmark (SPY) para el Beta
    if 'SPY' in data:
        spy_close = data['SPY']['Close'] if isinstance(data.columns, pd.MultiIndex) else data['Close']
        spy_returns = spy_close.pct_change().dropna()
    else:
        spy_returns = pd.Series(dtype=float)

    # Instanciar DataProvider (maneja Polygon, AlphaVantage, yf y caché)
    provider = DataProvider()
    
    # Descarga rápida de fundamentales (Market Cap, Target Price)
    fundamentals = {}
    quality_monitor = DataQualityMonitor()
    mc_engine = MonteCarloEngine(simulations=5000, time_horizon_days=30)
    now = pd.Timestamp.now()
    
    def get_info(t):
        try:
            quote = provider.get_quote(t)
            # Evaluar calidad (ej. EPS que suele ser crítico)
            eps_dp = quality_monitor.assess(t, 'eps', quote.eps, now)
            badge = quality_monitor.render_quality_badge(eps_dp)
            
            return t, quote.market_cap, quote.target_price, eps_dp.value, \
                   quote.growth, quote.roe, quote.op_margin, quote.debt_equity, badge
        except Exception as e:
            return t, None, None, None, 0.05, None, None, None, "⚫ yfinance"
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for t, mcap, tgt, eps, growth, roe, op_margin, debt_eq, badge in executor.map(get_info, tickers):
            growth_clamped = max(-0.10, min(growth, 0.30)) if growth is not None else 0.05
            fundamentals[t] = {
                'market_cap': mcap, 'target_price': tgt, 'eps': eps, 
                'growth': growth_clamped, 'roe': roe, 'op_margin': op_margin, 
                'debt_equity': debt_eq, 'quality_badge': badge
            }

    for ticker in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data:
                    continue
                df_t = data[ticker].copy()
            else:
                if ticker != tickers[0]: # Solo hay 1 ticker
                    continue
                df_t = data.copy()
            
            df_t = df_t.dropna(subset=['Close'])
            if len(df_t) < 20:
                continue
                
            current_price = float(df_t['Close'].iloc[-1])
            
            # Medias Móviles
            ma20 = float(df_t['Close'].rolling(window=20).mean().iloc[-1])
            ma50 = float(df_t['Close'].rolling(window=50).mean().iloc[-1])
            ma200 = float(df_t['Close'].rolling(window=200).mean().iloc[-1]) if len(df_t) >= 200 else np.nan
            
            # Volatilidad (Anualizada)
            returns = df_t['Close'].pct_change().dropna()
            volatility = float(returns.std() * np.sqrt(252))
            
            # Beta
            beta = 1.0
            if not spy_returns.empty and len(returns) > 30:
                # Alinear índices
                aligned = pd.concat([returns, spy_returns], axis=1).dropna()
                if len(aligned) > 30:
                    cov = np.cov(aligned.iloc[:,0], aligned.iloc[:,1])[0,1]
                    var = np.var(aligned.iloc[:,1])
                    beta = float(cov / var) if var != 0 else 1.0
                    
            # ATR (Average True Range - 14 días)
            high_low = df_t['High'] - df_t['Low']
            high_close = np.abs(df_t['High'] - df_t['Close'].shift())
            low_close = np.abs(df_t['Low'] - df_t['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            atr = float(true_range.rolling(14).mean().iloc[-1])
            
            
            # Monte Carlo VaR y CVaR
            mc_metrics = mc_engine.simulate(ticker=ticker, current_price=current_price, hist_prices=df_t['Close'])
            var_pct = mc_metrics.var_95_pct
            cvar_pct = mc_metrics.cvar_95_pct
            
            fund = fundamentals.get(ticker, {})
            results.append({
                'ticker': ticker,
                'current_price': current_price,
                'ma20': ma20,
                'ma50': ma50,
                'ma200': ma200,
                'volatility': volatility,
                'beta': beta,
                'atr': atr,
                'market_cap': fund.get('market_cap'),
                'target_price': fund.get('target_price'),
                'eps': fund.get('eps'),
                'growth': fund.get('growth'),
                'roe': fund.get('roe'),
                'op_margin': fund.get('op_margin'),
                'debt_equity': fund.get('debt_equity'),
                'quality': fund.get('quality_badge', '⚫ yfinance'),
                'var_95_pct': var_pct,
                'cvar_95_pct': cvar_pct
            })
        except Exception as e:
            print(f"Error procesando {ticker}: {e}")
            
    df_results = pd.DataFrame(results)
    
    # Calcular Z-Scores usando el CompositeScorer
    if not df_results.empty:
        scorer = CompositeScorer()
        df_scores = scorer.score_universe(fundamentals, data)
        if not df_scores.empty:
            df_scores['ticker'] = df_scores.index
            df_results = pd.merge(df_results, df_scores, on='ticker', how='left')
            
    return df_results

def _score_metric(value, low, high, invert=False, neutral=50):
    """Escala 'value' linealmente a un score 0-100 entre low y high."""
    if value is None:
        return neutral
    try:
        val = float(value)
    except (TypeError, ValueError):
        return neutral
    if invert:
        val, low, high = -val, -high, -low
    if val <= low:
        return 0.0
    if val >= high:
        return 100.0
    return (val - low) / (high - low) * 100.0

def calculate_quality_score(row):
    """Quality Score real (0-100) basado en ROE, margen operativo y apalancamiento."""
    roe = row.get('roe')
    op_margin = row.get('op_margin')
    debt_eq = row.get('debt_equity')

    roe_score = _score_metric(roe, low=0.05, high=0.30)
    margin_score = _score_metric(op_margin, low=0.05, high=0.35)
    debt_score = _score_metric(debt_eq, low=0, high=250, invert=True)

    return round((roe_score * 0.35) + (margin_score * 0.35) + (debt_score * 0.30), 1)

def calculate_scores(row, quality_score_default=85):
    """
    Calcula los scores institucionales en base a datos técnicos y fundamentales.
    Retorna un diccionario con los scores, la señal y debug info.
    """
    # ─── 1. TrendScore (0-100) ───
    trend_score = 0
    price = row.get('current_price', 0)
    ma20 = row.get('ma20', np.nan)
    ma50 = row.get('ma50', np.nan)
    ma200 = row.get('ma200', np.nan)

    if pd.notna(ma20) and price > ma20: trend_score += 20
    if pd.notna(ma50) and price > ma50: trend_score += 30
    if pd.notna(ma200) and price > ma200: trend_score += 30
    if pd.notna(ma50) and pd.notna(ma200) and ma50 > ma200: trend_score += 20

    # ─── 2. RiskScore (0-100) → Menor es mejor ───
    vol = row.get('volatility', 0.25)
    beta = row.get('beta', 1.0)

    risk_vol = min(max((vol - 0.10) / 0.40 * 100, 0), 100)
    risk_beta = min(max((beta - 0.5) / 1.5 * 100, 0), 100)
    risk_score = (risk_vol * 0.6) + (risk_beta * 0.4)

    # ─── 3. ValueScore (0-100) ───
    mos = row.get('margin_of_safety', 0.0)
    # ─── FIX: Manejar MOS de ETFs (puede ser pequeño negativo por premium) ───
    if mos is None:
        value_score = 10
    elif mos > 0.40:
        value_score = 100
    elif mos > 0.20:
        value_score = 80
    elif mos > 0:
        value_score = 60
    elif mos > -0.05:  # ETFs con pequeño premium
        value_score = 40
    elif mos > -0.20:
        value_score = 20
    else:
        value_score = 10

    # ─── 4. Quality Score ───
    quality_score = calculate_quality_score(row)
    # ─── FIX: Usar default cuando no hay datos ───
    if quality_score is None or quality_score == 50:
        quality_score = quality_score_default

    # ─── 5. Conviction Score ───
    risk_inverted = 100 - risk_score
    conviction_score = (value_score * 0.35) + (trend_score * 0.25) + (quality_score * 0.20) + (risk_inverted * 0.20)

    # ─── 6. Señal ───
    # ─── FIX: Lógica más clara y con trazabilidad ───
    is_etf = row.get('ticker') in ['SPY', 'VOO', 'QQQ', 'QQQM', 'SMH', 'SPMO', 'DIA', 'IWM', 'VTI', 'VT']

    if mos < -0.05 and not is_etf:
        signal = "NO COMPRAR"
    elif mos < 0 and is_etf:
        signal = "NO COMPRAR"  # ETF con premium
    elif mos >= 0.30 and trend_score >= 60:
        signal = "COMPRA FUERTE"
    elif mos >= 0.30 and trend_score < 60:
        signal = "COMPRA"
    elif mos >= 0.10:
        signal = "ESPERAR"
    elif mos >= 0:
        signal = "NEUTRAL"
    else:
        signal = "NO COMPRAR"

    # ─── DEBUG INFO ───
    debug = {
        'ticker': row.get('ticker'),
        'price': price,
        'mos': mos,
        'trend_score': trend_score,
        'value_score': value_score,
        'quality_score': quality_score,
        'risk_score': risk_score,
        'conviction_score': conviction_score,
        'is_etf': is_etf,
        'signal_logic': f"mos={mos:.4f}, trend={trend_score}, is_etf={is_etf}"
    }

    logger.info(f"SIGNAL: {debug}")

    # ─── 7. Mapeo a Kelly y Probabilidad (Retrocompatibilidad UI) ───
    # Mapeo simple: Cada 10 pts sobre 40 de convicción equivale a ~2.5% de peso.
    kelly_fraction = max(0.0, (conviction_score - 40) / 60 * 0.15) if signal in ['COMPRA FUERTE', 'COMPRA'] else 0.0
    prob_success = conviction_score / 100.0

    return {
        'TrendScore': round(trend_score, 1),
        'RiskScore': round(risk_score, 1),
        'ValueScore': round(value_score, 1),
        'ConvictionScore': round(conviction_score, 1),
        'Signal': signal,
        'kelly_fraction': kelly_fraction,
        'prob_success': prob_success,
        '_debug': debug
    }
