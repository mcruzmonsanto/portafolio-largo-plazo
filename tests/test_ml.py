import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.ml_anomaly import PriceAnomalyDetector
from modules.ml_regime import MarketRegimeHMM

def test_price_anomaly_detector_no_data():
    detector = PriceAnomalyDetector()
    # Si le damos menos de 200 puntos, devuelve empty (por MA200)
    prices = pd.Series([100] * 50)
    res = detector.detect(prices)
    assert res.empty

def test_price_anomaly_detector_with_fake_data():
    detector = PriceAnomalyDetector()
    # Generar 250 dias de precios normales y 1 dia anómalo al final
    np.random.seed(42)
    prices_normal = np.random.normal(100, 2, 250)
    prices_normal[-1] = 150 # Anomalía masiva
    
    series = pd.Series(prices_normal, index=pd.date_range('2025-01-01', periods=250))
    res = detector.detect(series)
    
    assert not res.empty
    # El último día debería estar marcado como anomalía o tener un score muy negativo
    assert res.iloc[-1]['is_anomaly'] == True

def test_market_regime_gmm_unfitted():
    model = MarketRegimeHMM()
    # Sin llamar a fit()
    res = model.predict_current()
    assert res['current_regime'] == 'Unknown (HMM no entrenado)'
    assert res['confidence'] == 0.0
