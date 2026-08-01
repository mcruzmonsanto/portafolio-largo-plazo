import yfinance as yf
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self):
        self.spy_ticker = "SPY"
        self.vix_ticker = "^VIX"
        
    def detect_market_regime(self) -> dict:
        """
        Determina el régimen actual de mercado y devuelve un multiplicador de riesgo 
        junto con un objetivo de liquidez sugerido.
        """
        try:
            # Extraer 250 días de SPY para calcular SMA 200
            spy_data = yf.download(self.spy_ticker, period="1y", progress=False)['Close']
            vix_data = yf.download(self.vix_ticker, period="1mo", progress=False)['Close']
            
            if spy_data.empty or vix_data.empty:
                raise ValueError("No se pudieron obtener datos del mercado.")
                
            current_spy = float(spy_data.iloc[-1].item() if isinstance(spy_data.iloc[-1], pd.Series) else spy_data.iloc[-1])
            sma_200 = float(spy_data.tail(200).mean().item() if isinstance(spy_data.tail(200).mean(), pd.Series) else spy_data.tail(200).mean())
            current_vix = float(vix_data.iloc[-1].item() if isinstance(vix_data.iloc[-1], pd.Series) else vix_data.iloc[-1])
            
            regime = "Bull Market"
            risk_multiplier = 1.0
            cash_target = 0.05  # 5% cash mínimo en tiempos buenos
            
            if current_spy < sma_200:
                regime = "Bear Market"
                risk_multiplier = 0.5  # Cortar riesgo a la mitad (Quarter-Kelly)
                cash_target = 0.25     # 25% cash mínimo en bear market
                
            if current_vix > 30:
                regime = "Panic / High Volatility"
                risk_multiplier = 0.4  # Pánico extremo
                cash_target = 0.30
                
            elif current_vix > 20 and current_spy >= sma_200:
                regime = "Correction / Volatile Bull"
                risk_multiplier = 0.75
                cash_target = 0.15
                
            return {
                "regime": regime,
                "risk_multiplier": risk_multiplier,
                "cash_target": cash_target,
                "spy_price": current_spy,
                "spy_sma200": sma_200,
                "vix": current_vix
            }
            
        except Exception as e:
            logger.error(f"Error detectando régimen: {e}")
            # Fallback seguro
            return {
                "regime": "Unknown (Fallback)",
                "risk_multiplier": 1.0,
                "cash_target": 0.10,
                "spy_price": 0,
                "spy_sma200": 0,
                "vix": 0
            }
