import pandas as pd
from typing import List, Dict
from modules.quant_engine import fetch_quant_data
from modules.signal_engine import BayesianSignal
from modules.valuation import calculate_fair_value

# Definición de universos pre-empaquetados para no sobrecargar las APIs
UNIVERSES = {
    "Dow Jones 30": ["AAPL", "MSFT", "JPM", "V", "PG", "UNH", "JNJ", "HD", "CVX", "MRK", "KO", "CSCO", "PEP", "MCD", "WMT", "CRM", "IBM", "TRV", "AMGN", "HON", "BA", "CAT", "GS", "DIS", "NKE", "MMM", "AXP", "DOW", "INTC", "VZ"],
    "Big Tech (FAAMG+)": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "ADBE", "CRM"],
    "Semiconductores": ["NVDA", "TSM", "AVGO", "ASML", "AMD", "QCOM", "TXN", "INTC", "AMAT", "MU"]
}

class AutoScanner:
    def __init__(self):
        self.signal_engine = BayesianSignal(payoff_ratio=3.0)

    def _calc_mos(self, row):
        eps = row.get('eps') or 0
        growth = row.get('growth') or 0.05
        price = row.get('current_price') or 0
        if eps and eps > 0 and price > 0:
            val = calculate_fair_value(eps, 15, growth * 100, price)
            return val['margin_of_safety']
        return -1.0

    def scan_universe(self, universe_name: str, min_kelly: float = 0.05) -> pd.DataFrame:
        """
        Escanea el universo y retorna solo las acciones que:
        - Tienen señal de COMPRA o COMPRA FUERTE.
        - Tienen un Kelly target por encima de min_kelly.
        """
        if universe_name not in UNIVERSES:
            raise ValueError(f"Universo no reconocido: {universe_name}")
            
        tickers = UNIVERSES[universe_name]
        df = fetch_quant_data(tickers)
        
        if df.empty:
            return pd.DataFrame()
            
        # Calcular Margen de Seguridad
        df['margin_of_safety'] = df.apply(self._calc_mos, axis=1)
        
        # Calcular Señales Bayesianas
        w_scores = df.apply(lambda r: self.signal_engine.generate_signal(r.get('composite_z', 0), r.get('margin_of_safety', 0)), axis=1)
        w_scores_df = pd.DataFrame(list(w_scores))
        df = pd.concat([df, w_scores_df], axis=1)
        
        # Filtrar oportunidades
        opportunities = df[(df['Signal'].isin(['COMPRA FUERTE', 'COMPRA'])) & (df['kelly_fraction'] >= min_kelly)]
        
        # Ordenar por Probabilidad de Éxito y Kelly
        if not opportunities.empty:
            opportunities = opportunities.sort_values(by=['prob_success', 'kelly_fraction'], ascending=[False, False])
            
        return opportunities
