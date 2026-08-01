import yfinance as yf
import pandas as pd
import numpy as np
import concurrent.futures

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
        # Descargamos 1 año de datos diarios
        data = yf.download(tickers_with_spy, period="1y", interval="1d", group_by='ticker', auto_adjust=True, progress=False)
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

    # Descarga rápida de fundamentales (Market Cap, Target Price)
    fundamentals = {}
    def get_info(t):
        try:
            info = yf.Ticker(t).info
            return t, info.get('marketCap'), info.get('targetMeanPrice')
        except:
            return t, None, None
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for t, mcap, tgt in executor.map(get_info, tickers):
            fundamentals[t] = {'market_cap': mcap, 'target_price': tgt}

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
                'target_price': fund.get('target_price')
            })
        except Exception as e:
            print(f"Error procesando {ticker}: {e}")
            
    return pd.DataFrame(results)

def calculate_scores(row, quality_score_default=85):
    """
    Calcula los scores institucionales en base a datos técnicos y fundamentales.
    Retorna un diccionario con los scores y la señal.
    """
    # 1. TrendScore (0-100)
    trend_score = 0
    price = row.get('current_price', 0)
    ma20 = row.get('ma20', np.nan)
    ma50 = row.get('ma50', np.nan)
    ma200 = row.get('ma200', np.nan)
    
    if pd.notna(ma20) and price > ma20: trend_score += 20
    if pd.notna(ma50) and price > ma50: trend_score += 30
    if pd.notna(ma200) and price > ma200: trend_score += 30
    if pd.notna(ma50) and pd.notna(ma200) and ma50 > ma200: trend_score += 20
    
    # 2. RiskScore (0-100) -> Menor es mejor
    vol = row.get('volatility', 0.25)
    beta = row.get('beta', 1.0)
    
    risk_vol = min(max((vol - 0.10) / 0.40 * 100, 0), 100)
    risk_beta = min(max((beta - 0.5) / 1.5 * 100, 0), 100)
    risk_score = (risk_vol * 0.6) + (risk_beta * 0.4)
    
    # 3. ValueScore (0-100)
    mos = row.get('margin_of_safety', 0.0) 
    if mos > 0.40:
        value_score = 100
    elif mos > 0.20:
        value_score = 80
    elif mos > 0:
        value_score = 60
    elif mos > -0.20:
        value_score = 40
    else:
        value_score = 10
        
    # 4. Quality Score
    quality_score = quality_score_default
    
    # 5. Conviction Score (Ponderación Maestro)
    risk_inverted = 100 - risk_score
    conviction_score = (value_score * 0.35) + (trend_score * 0.25) + (quality_score * 0.20) + (risk_inverted * 0.20)
    
    # 6. Señal (Nuevo requerimiento del usuario)
    if conviction_score >= 75:
        signal = "COMPRA FUERTE"
    elif conviction_score >= 60:
        signal = "COMPRA"
    elif conviction_score >= 45:
        signal = "ESPERAR"
    else:
        signal = "NO COMPRAR"
        
    return {
        'TrendScore': round(trend_score, 1),
        'RiskScore': round(risk_score, 1),
        'ValueScore': round(value_score, 1),
        'ConvictionScore': round(conviction_score, 1),
        'Signal': signal
    }
