import math

class BayesianSignal:
    def __init__(self, payoff_ratio: float = 3.0, risk_multiplier: float = 1.0):
        """
        payoff_ratio: (Ganancia Promedio / Pérdida Promedio).
        risk_multiplier: Factor de ajuste conservador aplicado al Kelly (0 a 1).
        Por defecto 3.0 asume que los ganadores rinden 3x más que lo que se pierde en los perdedores.
        """
        self.payoff_ratio = payoff_ratio
        self.risk_multiplier = risk_multiplier
        
    def _sigmoid(self, x: float) -> float:
        """Función logística estándar"""
        return 1 / (1 + math.exp(-x))

    def generate_signal(self, composite_z: float, margin_of_safety: float) -> dict:
        """
        Genera la probabilidad de éxito (0-1) y el Kelly Target Weight.
        
        Modelo Heurístico (Pre-Calibrado):
        Dado que no hay backtests masivos para entrenar un modelo ML real, 
        usamos una regresión logística teórica donde:
        - Un Z-Score de 0 y un MoS de 0% = 50% de probabilidad de éxito.
        - Cada +1 Z-Score sube el odds ratio.
        - Cada +10% MoS sube el odds ratio.
        """
        # x = B0 + B1*Z + B2*MoS
        # B0 = 0 (Base = 50%)
        # B1 = 0.8 (Un Z=+1 empuja p a ~69%)
        # B2 = 5.0 (Un MoS=+20% (+0.2) empuja p a ~73%)
        
        # Limitar valores extremos
        z_safe = max(-3.0, min(3.0, composite_z))
        mos_safe = max(-1.0, min(1.0, margin_of_safety))
        
        logit = (0.8 * z_safe) + (5.0 * mos_safe)
        
        prob_success = self._sigmoid(logit)
        
        # Criterio de Kelly
        # f* = (p*b - q) / b
        # p = prob_success, q = 1 - p, b = payoff_ratio
        p = prob_success
        q = 1.0 - p
        b = self.payoff_ratio
        
        full_kelly = (p * b - q) / b
        
        # Half-Kelly (más conservador) y ajuste por multiplicador
        half_kelly = max(0.0, full_kelly * 0.5)
        adjusted_kelly = half_kelly * self.risk_multiplier
        
        signal_label = self._classify(p, adjusted_kelly)
        
        return {
            'prob_success': prob_success,
            'kelly_fraction': adjusted_kelly,
            'Signal': signal_label
        }
        
    def _classify(self, p: float, kelly: float) -> str:
        if p > 0.70 and kelly > 0.15:
            return "COMPRA FUERTE"
        elif p > 0.55 and kelly > 0.05:
            return "COMPRA"
        elif p > 0.45:
            return "ESPERAR"
        else:
            return "NO COMPRAR"
