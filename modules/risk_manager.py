import numpy as np
import yfinance as yf
from enum import Enum
from dataclasses import dataclass

class MarketRegime(Enum):
    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR = "bear"
    RECOVERY = "recovery"
    CRISIS = "crisis"

@dataclass
class RiskProfile:
    regime: MarketRegime
    min_cash: float
    max_stock_weight: float
    max_etf_weight: float
    max_sector_exposure: float
    var_limit_daily: float  # Máximo VaR 95% diario permitido

class DynamicRiskManager:
    """
    Gestor de riesgo que adapta los límites del portafolio según el régimen de mercado.
    """
    
    # Perfiles por régimen
    PROFILES = {
        MarketRegime.BULL_LOW_VOL: RiskProfile(
            regime=MarketRegime.BULL_LOW_VOL,
            min_cash=0.05,
            max_stock_weight=0.15,
            max_etf_weight=0.70,
            max_sector_exposure=0.30,
            var_limit_daily=0.015  # 1.5% diario
        ),
        MarketRegime.BULL_HIGH_VOL: RiskProfile(
            regime=MarketRegime.BULL_HIGH_VOL,
            min_cash=0.10,
            max_stock_weight=0.10,
            max_etf_weight=0.60,
            max_sector_exposure=0.25,
            var_limit_daily=0.025
        ),
        MarketRegime.RECOVERY: RiskProfile(
            regime=MarketRegime.RECOVERY,
            min_cash=0.15,
            max_stock_weight=0.10,
            max_etf_weight=0.50,
            max_sector_exposure=0.20,
            var_limit_daily=0.020
        ),
        MarketRegime.BEAR: RiskProfile(
            regime=MarketRegime.BEAR,
            min_cash=0.30,
            max_stock_weight=0.05,
            max_etf_weight=0.30,
            max_sector_exposure=0.15,
            var_limit_daily=0.010
        ),
        MarketRegime.CRISIS: RiskProfile(
            regime=MarketRegime.CRISIS,
            min_cash=0.50,
            max_stock_weight=0.02,
            max_etf_weight=0.10,
            max_sector_exposure=0.10,
            var_limit_daily=0.005
        )
    }
    
    def __init__(self):
        self.spy = yf.Ticker("SPY")
        self.vix = yf.Ticker("^VIX")
    
    def detect_market_regime(self) -> dict:
        """
        Detecta el régimen actual (para compatibilidad con app.py original).
        """
        spy_hist = self.spy.history(period="2y")
        vix_hist = self.vix.history(period="30d")
        
        if spy_hist.empty or vix_hist.empty:
            return {
                'regime': 'Recovery',
                'spy_price': 0,
                'spy_sma200': 0,
                'vix': 0,
                'cash_target': 0.15,
                'risk_multiplier': 1.0
            }
        
        current_spy = spy_hist['Close'].iloc[-1]
        sma200 = spy_hist['Close'].rolling(200).mean().iloc[-1]
        sma50 = spy_hist['Close'].rolling(50).mean().iloc[-1]
        vix_current = vix_hist['Close'].iloc[-1]
        
        peak = spy_hist['Close'].cummax().iloc[-1]
        drawdown = (current_spy - peak) / peak
        
        if drawdown < -0.20:
            regime = 'Panic'
            cash_target = 0.50
            risk_multiplier = 0.5
        elif drawdown < -0.10:
            regime = 'Bear'
            cash_target = 0.30
            risk_multiplier = 0.8
        elif current_spy < sma200 and vix_current > 25:
            regime = 'Bear'
            cash_target = 0.30
            risk_multiplier = 0.8
        elif current_spy > sma200 and vix_current > 20:
            regime = 'Bull High Vol'
            cash_target = 0.10
            risk_multiplier = 1.0
        elif current_spy > sma200 and current_spy > sma50 and vix_current < 20:
            regime = 'Bull Low Vol'
            cash_target = 0.05
            risk_multiplier = 1.2
        else:
            regime = 'Recovery'
            cash_target = 0.15
            risk_multiplier = 1.0
            
        return {
            'regime': regime,
            'spy_price': current_spy,
            'spy_sma200': sma200,
            'vix': vix_current,
            'cash_target': cash_target,
            'risk_multiplier': risk_multiplier
        }
    
    def detect_regime(self) -> MarketRegime:
        """
        Detecta el régimen actual (para el nuevo flujo).
        """
        data = self.detect_market_regime()
        regime_str = data['regime']
        if regime_str == 'Panic': return MarketRegime.CRISIS
        elif regime_str == 'Bear': return MarketRegime.BEAR
        elif regime_str == 'Bull High Vol': return MarketRegime.BULL_HIGH_VOL
        elif regime_str == 'Bull Low Vol': return MarketRegime.BULL_LOW_VOL
        return MarketRegime.RECOVERY
    
    def get_current_profile(self) -> RiskProfile:
        regime = self.detect_regime()
        return self.PROFILES[regime]
    
    def check_portfolio_compliance(self, portfolio) -> dict:
        """
        Verifica si el portafolio cumple con el perfil de riesgo actual.
        """
        profile = self.get_current_profile()
        violations = []
        
        # 1. Cash mínimo
        cash_pct = portfolio.cash / portfolio.nav
        if cash_pct < profile.min_cash:
            violations.append({
                'type': 'CASH_MINIMUM',
                'severity': 'CRITICAL',
                'current': cash_pct,
                'required': profile.min_cash,
                'action': f'Vender activos para alcanzar {profile.min_cash*100:.0f}% cash'
            })
        
        # 2. Pesos individuales
        for pos in portfolio.positions:
            max_w = profile.max_etf_weight if pos.is_etf else profile.max_stock_weight
            if pos.weight > max_w:
                violations.append({
                    'type': 'POSITION_LIMIT',
                    'severity': 'HIGH',
                    'ticker': pos.ticker,
                    'current': pos.weight,
                    'limit': max_w,
                    'action': f'Reducir {pos.ticker} a {max_w*100:.0f}%'
                })
        
        # 3. VaR diario
        var_95 = portfolio.calculate_var(0.95, 1)
        if var_95 > profile.var_limit_daily * portfolio.nav:
            violations.append({
                'type': 'VAR_LIMIT',
                'severity': 'HIGH',
                'current_var': var_95,
                'limit': profile.var_limit_daily * portfolio.nav,
                'action': 'Reducir exposición o agregar hedges'
            })
        
        # 4. Exposición sectorial
        sector_exposure = portfolio.get_sector_exposure()
        for sector, weight in sector_exposure.items():
            if weight > profile.max_sector_exposure:
                violations.append({
                    'type': 'SECTOR_LIMIT',
                    'severity': 'MEDIUM',
                    'sector': sector,
                    'current': weight,
                    'limit': profile.max_sector_exposure,
                    'action': f'Diversificar fuera de {sector}'
                })
        
        return {
            'regime': profile.regime.value,
            'profile': profile,
            'compliant': len(violations) == 0,
            'violations': violations,
            'recommendations': self._generate_recommendations(violations, profile)
        }
    
    def _generate_recommendations(self, violations, profile):
        """Genera acciones correctivas priorizadas."""
        if not violations:
            return ["Portafolio dentro de parámetros. Mantener disciplina."]
        
        recs = []
        for v in sorted(violations, key=lambda x: {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}[x['severity']]):
            recs.append(f"[{v['severity']}] {v['type']}: {v['action']}")
        
        return recs
