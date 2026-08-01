import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List

class CompositeScorer:
    def __init__(self):
        # Pesos institucionales pre-calibrados por IC (Information Coefficient)
        self.weights = {
            'value': 0.30,
            'quality': 0.30,
            'momentum': 0.25,
            'risk': 0.15
        }
        
    def _winsorize_and_zscore(self, series: pd.Series) -> pd.Series:
        """Aplica winsorización al 1%/99% y calcula el Z-Score cross-sectional"""
        if len(series) == 0:
            return series
            
        # Winsorize
        lower, upper = np.percentile(series.dropna(), [1, 99])
        clipped = series.clip(lower=lower, upper=upper)
        
        # Z-Score
        mean = clipped.mean()
        std = clipped.std()
        
        if std == 0 or pd.isna(std):
            return pd.Series(0, index=series.index)
            
        return (clipped - mean) / std

    def score_universe(self, fundamentals: dict, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        Toma los fundamentales y el histórico de precios para emitir
        un DataFrame con los Z-Scores y el Percentil.
        """
        tickers = list(fundamentals.keys())
        if not tickers:
            return pd.DataFrame()
            
        df_fund = pd.DataFrame.from_dict(fundamentals, orient='index')
        
        # --- 1. FACTOR: VALUE (Invertido, menor múltiplo es mejor) ---
        # Aproximamos Value usando P/E (Price / EPS)
        # EPS = df_fund['eps']
        # Usaremos E/P (Earnings Yield) para evitar divisiones por cero o negativos en P/E
        earnings_yield = df_fund.apply(
            lambda x: x['eps'] / x['current_price'] if pd.notna(x.get('eps')) and x.get('current_price', 0) > 0 else 0,
            axis=1
        )
        z_value = self._winsorize_and_zscore(earnings_yield)
        
        # --- 2. FACTOR: QUALITY ---
        # ROE + Margen Operativo - (Debt/Equity / 100)
        roe = df_fund['roe'].fillna(df_fund['roe'].median())
        margin = df_fund['op_margin'].fillna(df_fund['op_margin'].median())
        debt_eq = df_fund['debt_equity'].fillna(df_fund['debt_equity'].median()) / 100.0
        
        quality_raw = (roe * 0.4) + (margin * 0.4) - (debt_eq * 0.2)
        z_quality = self._winsorize_and_zscore(quality_raw)
        
        # --- 3. FACTOR: MOMENTUM ---
        # Retorno de 6 meses y 3 meses (asumiendo 126 y 63 días de trading en la data histórica)
        momentum_raw = pd.Series(0.0, index=tickers)
        for t in tickers:
            if t in price_data:
                close = price_data[t]['Close'] if isinstance(price_data.columns, pd.MultiIndex) else price_data['Close']
                if len(close) > 126:
                    ret_6m = (close.iloc[-1] / close.iloc[-126]) - 1
                    ret_3m = (close.iloc[-1] / close.iloc[-63]) - 1
                    momentum_raw[t] = (ret_6m * 0.6) + (ret_3m * 0.4)
        z_momentum = self._winsorize_and_zscore(momentum_raw)
        
        # --- 4. FACTOR: RISK (Invertido, menor riesgo es mejor) ---
        # Volatilidad (anualizada)
        risk_raw = pd.Series(0.0, index=tickers)
        for t in tickers:
            if t in price_data:
                close = price_data[t]['Close'] if isinstance(price_data.columns, pd.MultiIndex) else price_data['Close']
                if len(close) > 20:
                    returns = close.pct_change().dropna()
                    vol = returns.std() * np.sqrt(252)
                    risk_raw[t] = -vol  # Negativo porque menor vol es mejor
        z_risk = self._winsorize_and_zscore(risk_raw)
        
        # --- COMPOSITE SCORE ---
        df_scores = pd.DataFrame({
            'z_value': z_value,
            'z_quality': z_quality,
            'z_momentum': z_momentum,
            'z_risk': z_risk
        }, index=tickers)
        
        df_scores['composite_z'] = (
            df_scores['z_value'] * self.weights['value'] +
            df_scores['z_quality'] * self.weights['quality'] +
            df_scores['z_momentum'] * self.weights['momentum'] +
            df_scores['z_risk'] * self.weights['risk']
        )
        
        # Convertir a Percentil Normal (0-100)
        df_scores['percentile'] = df_scores['composite_z'].apply(lambda z: stats.norm.cdf(z) * 100)
        
        return df_scores
