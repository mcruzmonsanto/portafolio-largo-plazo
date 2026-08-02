import numpy as np
import pandas as pd
import yfinance as yf
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RiskMetrics:
    var_95_pct: float
    cvar_95_pct: float
    simulated_final_prices: np.ndarray

class MonteCarloEngine:
    def __init__(self, simulations: int = 10000, time_horizon_days: int = 30):
        self.simulations = simulations
        self.time_horizon = time_horizon_days
        
    def _fetch_history(self, ticker: str, period: str = "2y") -> pd.Series:
        """Descarga historial para calcular drift y volatilidad diaria."""
        try:
            data = yf.download(ticker, period=period, progress=False)
            if data.empty:
                return pd.Series()
            return data['Close'].squeeze()
        except Exception as e:
            logger.error(f"Error descargando datos para Monte Carlo en {ticker}: {e}")
            return pd.Series()

    def simulate(self, ticker: str, current_price: float = None, hist_prices: pd.Series = None) -> RiskMetrics:
        """
        Ejecuta la simulación de Movimiento Browniano Geométrico y devuelve VaR y CVaR (Esperanza de pérdida extrema) al 95%.
        """
        if hist_prices is not None and not hist_prices.empty:
            prices = hist_prices
        else:
            prices = self._fetch_history(ticker)
        
        if len(prices) < 252:
            # Fallback si no hay suficientes datos
            logger.warning(f"Insuficientes datos históricos para MC en {ticker}")
            return RiskMetrics(var_95_pct=0.0, cvar_95_pct=0.0, simulated_final_prices=np.array([]))

        # 1. Calcular retornos diarios continuos
        log_returns = np.log(1 + prices.pct_change().dropna())
        
        # 2. Calcular Drift y Volatilidad
        u = log_returns.mean()
        var = log_returns.var()
        drift = u - (0.5 * var)
        stdev = log_returns.std()
        
        # Último precio conocido o inyectado
        p0 = current_price if current_price else prices.iloc[-1]
        if isinstance(p0, pd.Series):
            p0 = p0.item()
            
        # 3. Generar caminos aleatorios usando numpy de forma vectorizada
        # Z es un arreglo 2D de dimensiones (días, simulaciones) con normales estándar
        # Fijamos semilla para evitar parpadeos enormes en UI
        np.random.seed(42)
        Z = np.random.standard_normal((self.time_horizon, self.simulations))
        
        # Calcular los retornos simulados por cada día y simulación
        daily_returns = np.exp(drift + stdev * Z)
        
        # Multiplicamos acumulativamente partiendo del precio base
        price_paths = np.zeros_like(daily_returns)
        price_paths[0] = p0 * daily_returns[0]
        
        for t in range(1, self.time_horizon):
            price_paths[t] = price_paths[t-1] * daily_returns[t]
            
        # Tomar los precios finales
        final_prices = price_paths[-1]
        
        # Calcular retornos porcentuales finales contra p0
        final_returns_pct = (final_prices - p0) / p0
        
        # 4. Extraer VaR y CVaR (95%)
        # El percentil 5 representa el corte del peor 5% de los escenarios
        var_95 = np.percentile(final_returns_pct, 5)
        
        # CVaR: Promedio de todos los escenarios que caen debajo del VaR
        tail_losses = final_returns_pct[final_returns_pct <= var_95]
        cvar_95 = tail_losses.mean() if len(tail_losses) > 0 else var_95
        
        return RiskMetrics(
            var_95_pct=float(var_95),
            cvar_95_pct=float(cvar_95),
            simulated_final_prices=final_prices
        )
