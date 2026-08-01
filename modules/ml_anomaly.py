import pandas as pd
from sklearn.ensemble import IsolationForest
import logging

logger = logging.getLogger(__name__)

class PriceAnomalyDetector:
    def __init__(self):
        self.model = IsolationForest(
            contamination=0.05,  # Esperamos 5% de anomalías
            random_state=42,
            n_estimators=100
        )
    
    def detect(self, prices: pd.Series) -> pd.DataFrame:
        """Detecta movimientos de precio anómalos"""
        try:
            if len(prices) < 200:
                return pd.DataFrame()
                
            # Features: retornos, volatilidad móvil, volumen relativo
            features = pd.DataFrame({
                'return_1d': prices.pct_change(),
                'return_5d': prices.pct_change(5),
                'volatility_20d': prices.pct_change().rolling(20).std(),
                'price_vs_ma50': prices / prices.rolling(50).mean() - 1,
                'price_vs_ma200': prices / prices.rolling(200).mean() - 1
            }).dropna()
            
            if features.empty:
                return pd.DataFrame()
                
            self.model.fit(features)
            predictions = self.model.predict(features)
            scores = self.model.decision_function(features)
            
            df_result = pd.DataFrame({
                'date': features.index,
                'is_anomaly': predictions == -1,
                'anomaly_score': scores,
                'price': prices.loc[features.index]
            })
            
            # Devolver solo la última fecha si es anomalía, o el DataFrame entero para debugging
            return df_result
        except Exception as e:
            logger.error(f"Error en detección de anomalías: {e}")
            return pd.DataFrame()
