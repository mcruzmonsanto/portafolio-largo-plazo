import pandas as pd
import numpy as np
import logging
from sklearn.mixture import GaussianMixture
from datetime import datetime, timedelta
import yfinance as yf
import traceback

logger = logging.getLogger(__name__)

class MarketRegimeHMM:
    def __init__(self, n_regimes=4):
        self.model = GaussianMixture(
            n_components=n_regimes,
            covariance_type="full",
            max_iter=100,
            random_state=42
        )
        # Nombres teóricos para los regímenes (serán asignados empíricamente tras el entrenamiento)
        self.regime_labels = {
            0: 'bull_low_vol',
            1: 'bull_high_vol', 
            2: 'bear',
            3: 'recovery'
        }
        self.is_fitted = False
    
    def _fetch_training_data(self) -> pd.DataFrame:
        """Descarga datos históricos de SPY y VIX para el entrenamiento"""
        try:
            # Necesitamos historial largo para identificar regímenes (ej. 5 años)
            data = yf.download(['SPY', '^VIX'], period="5y", interval="1d", group_by='ticker', auto_adjust=True, progress=False)
            
            # Formatear
            if isinstance(data.columns, pd.MultiIndex):
                spy_close = data['SPY']['Close']
                vix_close = data['^VIX']['Close']
            else:
                return pd.DataFrame()
                
            spy_returns = spy_close.pct_change().dropna()
            vix = vix_close.loc[spy_returns.index]
            
            features = pd.DataFrame({
                'returns': spy_returns,
                'returns_sq': spy_returns ** 2,
                'vix': vix
            }).dropna()
            
            return features
        except Exception as e:
            logger.error(f"Error descargando datos para HMM: {e}")
            return pd.DataFrame()

    def _assign_labels_to_states(self, features: pd.DataFrame, hidden_states: np.ndarray):
        """Asigna etiquetas de régimen reales basándose en la estadística de los estados ocultos"""
        features_with_states = features.copy()
        features_with_states['state'] = hidden_states
        
        # Agrupar y calcular estadísticas por estado
        state_stats = features_with_states.groupby('state').agg({
            'returns': 'mean',
            'vix': 'mean'
        })
        
        # Ordenar por VIX (los de menor volatilidad suelen ser Bull)
        # Esto es una heurística; los mercados reales requieren reglas para identificar qué estado HMM es qué régimen
        sorted_by_vix = state_stats.sort_values('vix')
        states_by_vix = sorted_by_vix.index.tolist()
        
        # Asumiendo 4 regímenes:
        # Menor VIX, retornos positivos -> Bull Low Vol
        # VIX medio, retornos altos -> Recovery o Bull High Vol
        # Mayor VIX, retornos negativos -> Bear
        
        # Esta es una aproximación robusta para remapear los estados HMM aleatorios a nombres legibles
        mapping = {}
        if len(states_by_vix) == 4:
            mapping[states_by_vix[0]] = 'Bull (Low Vol)'
            mapping[states_by_vix[1]] = 'Bull (High Vol)'
            mapping[states_by_vix[2]] = 'Recovery'
            mapping[states_by_vix[3]] = 'Bear Market'
        else:
            for i in range(len(states_by_vix)):
                mapping[states_by_vix[i]] = f"Regime {i}"
                
        self.regime_labels = mapping

    def fit(self):
        """Descarga datos y entrena el modelo"""
        try:
            features = self._fetch_training_data()
            if features.empty or len(features) < 100:
                logger.error("HMM Data insufficient")
                return self
                
            self.model.fit(features)
            self.is_fitted = True
            
            # Clasificamos qué estado es qué
            hidden_states = self.model.predict(features)
            self._assign_labels_to_states(features, hidden_states)
            
            self.features = features
        except Exception as e:
            logger.error(f"Error entrenando HMM: {e}\n{traceback.format_exc()}")
        return self
    
    def predict_current(self) -> dict:
        if not self.is_fitted:
            return {
                'current_regime': 'Unknown (HMM no entrenado)',
                'confidence': 0.0,
                'regime_probs': {},
                'expected_duration': 0
            }
            
        try:
            # Obtener las características de los últimos días
            latest_features = self.features.tail(10)
            if len(latest_features) == 0:
                raise ValueError("No hay features recientes")
                
            # Predecir estado actual (el último)
            regime_idx = self.model.predict(latest_features)[-1]
            probs = self.model.predict_proba(latest_features)[-1]
            
            regime_name = self.regime_labels.get(regime_idx, f"State {regime_idx}")
            
            return {
                'current_regime': regime_name,
                'confidence': float(max(probs)),
                'regime_probs': {
                    self.regime_labels.get(i, f"State {i}"): float(p) 
                    for i, p in enumerate(probs)
                },
                'expected_duration': self._estimate_duration(regime_idx),
                'vix_current': float(latest_features['vix'].iloc[-1])
            }
        except Exception as e:
            logger.error(f"Error en inferencia HMM: {e}")
            return {
                'current_regime': 'Error',
                'confidence': 0.0,
                'regime_probs': {},
                'expected_duration': 0
            }
    
    def _estimate_duration(self, regime: int) -> int:
        """Días esperados en este régimen basado en la media histórica"""
        return 21 # GMM no tiene matriz de transición, devolvemos 1 mes proxy
