import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist
from dataclasses import dataclass
from typing import Optional

@dataclass
class Signal:
    ticker: str
    action: str  # COMPRA_FUERTE, COMPRA, ESPERAR, NO_COMPRAR, REDUCIR
    probability: float  # Probabilidad posterior de éxito
    kelly_fraction: float  # f* óptima
    recommended_shares: int
    recommended_usd: float
    confidence_interval: tuple  # (lower, upper) 95%
    rationale: str

class BayesianSignalEngine:
    """
    Motor de inferencia bayesiana para señales de mercado.
    
    Prior: Beta(2, 2) → distribución uniforme moderada (poco sesgada)
    Likelihood: Bernoulli basado en evidencia histórica de señales similares
    Posterior: Beta(α + éxitos, β + fracasos)
    """
    
    def __init__(self, historical_db_path: str = "data/signal_history.parquet"):
        self.prior_alpha = 2.0
        self.prior_beta = 2.0
        self.history = self._load_history(historical_db_path)
        self.payoff_ratio = 2.5  # b = ganancia esperada / pérdida esperada
        
    def _load_history(self, path: str) -> pd.DataFrame:
        try:
            return pd.read_parquet(path)
        except FileNotFoundError:
            # Inicializar con datos sintéticos conservadores
            return pd.DataFrame({
                'mos_bucket': ['high', 'medium', 'low', 'negative'],
                'trend_bucket': ['strong', 'moderate', 'weak', 'negative'],
                'successes': [45, 30, 15, 5],
                'failures': [15, 25, 35, 45]
            })
    
    def _get_likelihood(self, mos: float, trend_score: float, quality_score: float) -> tuple:
        """
        Devuelve (éxitos, fracasos) observados para una combinación de señales similar.
        """
        # Discretizar señales en buckets
        mos_bucket = 'high' if mos > 0.30 else 'medium' if mos > 0.15 else 'low' if mos > 0 else 'negative'
        trend_bucket = 'strong' if trend_score > 70 else 'moderate' if trend_score > 50 else 'weak' if trend_score > 30 else 'negative'
        
        match = self.history[
            (self.history['mos_bucket'] == mos_bucket) & 
            (self.history['trend_bucket'] == trend_bucket)
        ]
        
        if match.empty:
            # Fallback: usar prior + penalización por falta de datos
            return (5, 5)  # Muy conservador
        
        return (match['successes'].iloc[0], match['failures'].iloc[0])
    
    def generate_signal(self, ticker: str, current_price: float, 
                       mos: float, trend_score: float, quality_score: float,
                       risk_score: float, portfolio_nav: float,
                       current_weight: float, max_weight: float,
                       available_cash: float) -> Signal:
        
        # ─── Inferencia Bayesiana ───
        successes, failures = self._get_likelihood(mos, trend_score, quality_score)
        
        # Posterior: Beta(α_prior + éxitos, β_prior + fracasos)
        posterior_alpha = self.prior_alpha + successes
        posterior_beta = self.prior_beta + failures
        
        # Probabilidad de éxito = media de la posterior
        p_success = posterior_alpha / (posterior_alpha + posterior_beta)
        
        # Intervalo de credibilidad 95%
        ci_lower = beta_dist.ppf(0.025, posterior_alpha, posterior_beta)
        ci_upper = beta_dist.ppf(0.975, posterior_alpha, posterior_beta)
        
        # ─── Kelly Criterion ───
        q = 1 - p_success
        kelly_raw = (p_success * self.payoff_ratio - q) / self.payoff_ratio
        
        # Kelly fraccional (más conservador para evitar ruin)
        kelly_fraction = max(0, kelly_raw * 0.25)  # Quarter Kelly
        
        # ─── Determinar acción ───
        if p_success < 0.45 or mos < 0:
            action = "NO_COMPRAR"
            kelly_fraction = 0
        elif p_success < 0.55:
            action = "ESPERAR"
            kelly_fraction = 0
        elif p_success < 0.65:
            action = "COMPRA"
        elif p_success >= 0.65:
            action = "COMPRA_FUERTE"
        
        # ─── Sizing respetando límites de riesgo ───
        space_left = max_weight - current_weight
        if space_left <= 0:
            action = "REDUCIR" if current_weight > max_weight else "MANTENER"
            kelly_fraction = 0
        
        max_investable = portfolio_nav * min(kelly_fraction, space_left)
        max_investable = min(max_investable, available_cash)
        
        recommended_shares = int(max_investable / current_price) if current_price > 0 else 0
        recommended_usd = recommended_shares * current_price
        
        # ─── Rationale ───
        rationale = (
            f"Probabilidad de éxito: {p_success:.1%} (IC 95%: {ci_lower:.1%}-{ci_upper:.1%}). "
            f"Kelly óptimo: {kelly_raw:.1%} → fraccional: {kelly_fraction:.1%}. "
            f"Espacio disponible: {space_left*100:.1f}%. "
            f"Cash disponible: ${available_cash:,.0f}."
        )
        
        return Signal(
            ticker=ticker,
            action=action,
            probability=p_success,
            kelly_fraction=kelly_fraction,
            recommended_shares=recommended_shares,
            recommended_usd=recommended_usd,
            confidence_interval=(ci_lower, ci_upper),
            rationale=rationale
        )
    
    def update_history(self, signal: Signal, actual_return_3m: float):
        """Actualizar historial con resultado real para mejorar prior."""
        # Si retorno > 10% en 3 meses = éxito
        is_success = actual_return_3m > 0.10
        
        # Agregar al historial (para próxima inferencia)
        new_row = {
            'date': pd.Timestamp.now(),
            'ticker': signal.ticker,
            'action': signal.action,
            'probability': signal.probability,
            'actual_return_3m': actual_return_3m,
            'success': is_success
        }
        # Append a parquet...
        new_df = pd.DataFrame([new_row])
        self.history = pd.concat([self.history, new_df], ignore_index=True)
