import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.signal_engine import BayesianSignal

def test_bayesian_signal_bull_buy():
    # En un bull market (risk_multiplier alto), el umbral de compra debería ser más fácil de alcanzar
    engine = BayesianSignal(payoff_ratio=3.0, risk_multiplier=1.2)
    
    # Buen Z-Score (barato) y margen de seguridad alto (MoS = 0.25 = 25%)
    signal = engine.generate_signal(composite_z=1.5, margin_of_safety=0.25)
    assert 'COMPRA' in signal['Signal']

def test_bayesian_signal_bear_wait():
    # En un bear market (risk_multiplier bajo), el sistema debe ser más estricto
    engine = BayesianSignal(payoff_ratio=3.0, risk_multiplier=0.6)
    
    # Z-Score neutral y margen de seguridad negativo (sobrevalorado)
    signal = engine.generate_signal(composite_z=-0.5, margin_of_safety=-0.10)
    assert signal['Signal'] in ['ESPERAR', 'NO COMPRAR']

def test_kelly_criterion_math():
    engine = BayesianSignal(payoff_ratio=3.0, risk_multiplier=1.0)
    # p_target ~= 0.70 (Z=0, MoS=0.17 -> logit=0.85 -> p=0.700)
    # p = 0.7, b = 3.0 -> full Kelly = (0.7*3 - 0.3)/3 = 1.8/3 = 0.60
    # half Kelly = 0.30
    signal = engine.generate_signal(composite_z=0.0, margin_of_safety=0.17)
    kelly = signal['kelly_fraction']
    assert 0.25 < kelly < 0.35

def test_kelly_zero_or_negative():
    engine = BayesianSignal(payoff_ratio=3.0, risk_multiplier=1.0)
    # Z-Score pesimo y MoS muy negativo
    signal = engine.generate_signal(composite_z=-3.0, margin_of_safety=-0.5)
    assert signal['kelly_fraction'] == 0.0
