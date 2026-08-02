import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.montecarlo import MonteCarloEngine

def test_montecarlo_engine_basic():
    engine = MonteCarloEngine(simulations=1000, time_horizon_days=30)
    
    # Generar fake historical prices (252 dias, de 100 a 110 con ruido)
    np.random.seed(42)
    fake_returns = np.random.normal(0.0005, 0.015, 252) # drift positivo
    fake_prices = 100 * np.exp(np.cumsum(fake_returns))
    
    series = pd.Series(fake_prices)
    
    res = engine.simulate(ticker="FAKE", current_price=series.iloc[-1], hist_prices=series)
    
    # El CVaR siempre debe ser menor o igual al VaR (son negativos, o sea, pérdidas más profundas)
    assert res.cvar_95_pct <= res.var_95_pct
    assert len(res.simulated_final_prices) == 1000
    
    # VaR para 30 días debería ser un porcentaje negativo razonable, ej. -5% a -15%
    assert -0.5 < res.var_95_pct < 0.0
    
def test_montecarlo_insufficient_data():
    engine = MonteCarloEngine()
    series = pd.Series([100]*100) # Solo 100 dias
    res = engine.simulate("FAKE", current_price=100, hist_prices=series)
    assert res.var_95_pct == 0.0
    assert res.cvar_95_pct == 0.0
