import yfinance as yf
import pandas as pd
import streamlit as st

@st.cache_data(ttl=900)  # Caché de 15 minutos. Retorna datos en memoria sin re-llamar a la API.
def fetch_live_data(tickers: list) -> pd.DataFrame:
    """
    Descarga precios actuales y datos fundamentales básicos para una lista de tickers.
    """
    if not tickers:
        return pd.DataFrame()
    
    data = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            
            # Obtener precio de la forma más robusta posible (fast_info o history)
            current_price = 0.0
            try:
                current_price = float(stock.fast_info.last_price)
            except Exception:
                try:
                    hist = stock.history(period="1d")
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])
                except Exception:
                    pass
            
            # Intentar obtener EPS y PE, pero si falla que no afecte al precio
            eps = 0.0
            pe = 0.0
            try:
                info = stock.info
                eps = info.get('trailingEps', 0.0) or 0.0
                pe = info.get('trailingPE', 0.0) or 0.0
            except Exception:
                pass # Silenciar fallos de .info (común en Streamlit Cloud por rate limiting)
                
            data.append({
                'ticker': ticker,
                'current_price': current_price,
                'eps': eps,
                'pe': pe
            })
        except Exception:
            data.append({
                'ticker': ticker,
                'current_price': 0.0,
                'eps': 0.0,
                'pe': 0.0
            })
            
    return pd.DataFrame(data)