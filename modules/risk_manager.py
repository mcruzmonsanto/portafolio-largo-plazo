import yfinance as yf
import pandas as pd
import logging
from modules.ml_regime import MarketRegimeHMM

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
            # Usamos el modelo ML para predecir el régimen
            hmm_engine = MarketRegimeHMM(n_regimes=4)
            hmm_engine.fit()
            ml_pred = hmm_engine.predict_current()
            
            ml_regime = ml_pred.get('current_regime', 'Unknown')
            current_vix = ml_pred.get('vix_current', 20.0)
            
            # Mapeo de régimen ML a reglas de riesgo
            regime = ml_regime
            risk_multiplier = 1.0
            cash_target = 0.05
            
            if "Bear" in regime:
                risk_multiplier = 0.5
                cash_target = 0.25
            elif "High Vol" in regime or "Recovery" in regime:
                risk_multiplier = 0.75
                cash_target = 0.15
            elif "Low Vol" in regime:
                risk_multiplier = 1.0
                cash_target = 0.05
                
            # Sobrescritura por pánico extremo
            if current_vix > 30:
                regime = "Panic / High Volatility"
                risk_multiplier = 0.4
                cash_target = 0.30
                
            return {
                "regime": f"{regime} (ML Confidence: {ml_pred.get('confidence', 0)*100:.0f}%)",
                "risk_multiplier": risk_multiplier,
                "cash_target": cash_target,
                "spy_price": current_spy,
                "spy_sma200": sma_200,
                "vix": current_vix,
                "ml_data": ml_pred
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
