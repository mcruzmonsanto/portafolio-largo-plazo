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
            info = stock.info
            
            # yfinance cambia sus llaves a veces; usamos .get para evitar Crash
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
            eps = info.get('trailingEps', 0.0)
            pe = info.get('trailingPE', 0.0)
            
            data.append({
                'ticker': ticker,
                'current_price': current_price,
                'eps': eps,
                'pe': pe
            })
        except Exception as e:
            # Silenciamos el error en la UI, pero evitamos que un ticker malo tumbe la app
            data.append({
                'ticker': ticker,
                'current_price': 0.0,
                'eps': 0.0,
                'pe': 0.0
            })
            
    return pd.DataFrame(data)