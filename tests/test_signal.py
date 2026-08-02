import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.signal_engine import BayesianSignalEngine, Signal

def test_bayesian_signal_bull_buy():
    engine = BayesianSignalEngine()
    
    # Simular una acción con excelente MoS y Trend Score
    signal = engine.generate_signal(
        ticker="AAPL", current_price=150.0,
        mos=0.35, trend_score=80.0, quality_score=90.0,
        risk_score=10.0, portfolio_nav=100000,
        current_weight=0.0, max_weight=0.10, available_cash=20000
    )
    # Por defecto prior es (2,2). likelihood de mos_bucket='high' trend_bucket='strong' 
    # asume (45, 15) que es p=47/64 = 0.73. Debe dar 'COMPRA_FUERTE'
    assert signal.action in ['COMPRA', 'COMPRA_FUERTE']

def test_bayesian_signal_bear_wait():
    engine = BayesianSignalEngine()
    
    # Simular MoS negativo y trend negativo
    signal = engine.generate_signal(
        ticker="AAPL", current_price=150.0,
        mos=-0.10, trend_score=20.0, quality_score=50.0,
        risk_score=90.0, portfolio_nav=100000,
        current_weight=0.0, max_weight=0.10, available_cash=20000
    )
    assert signal.action in ['ESPERAR', 'NO_COMPRAR']

def test_kelly_criterion_limits():
    engine = BayesianSignalEngine()
    signal = engine.generate_signal(
        ticker="AAPL", current_price=150.0,
        mos=0.35, trend_score=80.0, quality_score=90.0,
        risk_score=10.0, portfolio_nav=100000,
        current_weight=0.10, max_weight=0.10, available_cash=20000
    )
    # Ya está al límite de peso máximo
    assert signal.action == 'MANTENER'
    assert signal.kelly_fraction == 0.0

def test_kelly_zero_or_negative():
    engine = BayesianSignalEngine()
    signal = engine.generate_signal(
        ticker="AAPL", current_price=150.0,
        mos=-0.5, trend_score=20.0, quality_score=10.0,
        risk_score=90.0, portfolio_nav=100000,
        current_weight=0.0, max_weight=0.10, available_cash=20000
    )
    assert signal.kelly_fraction == 0.0
