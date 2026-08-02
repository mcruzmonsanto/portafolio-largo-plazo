import yfinance as yf
from portfolio_config import GRAHAM_WEIGHT, MULTIPLE_WEIGHT, KNOWN_ETFS

def calculate_fair_value(eps: float, target_pe: float, growth_rate: float, 
                         current_price: float, bond_yield: float = 4.4,
                         ticker: str = "") -> dict:
    """
    Calcula el Valor Intrínseco (Fair Value) combinando Graham y Múltiplos.
    Para ETFs, usa NAV-based valuation en lugar de EPS.
    """

    # ─── ETFs: Valoración por NAV ───
    if ticker in KNOWN_ETFS:
        return _calculate_etf_fair_value(ticker, current_price)

    # ─── Validación de inputs ───
    if eps is None or not isinstance(eps, (int, float)):
        eps = 0.0
    if current_price is None or not isinstance(current_price, (int, float)) or current_price <= 0:
        return _error_result("Invalid current_price")
    if eps <= 0:
        return _error_result("EPS <= 0", current_price)

    # Normalizar growth_rate
    if growth_rate is None or not isinstance(growth_rate, (int, float)):
        growth_rate = 5.0
    growth_rate = max(-10.0, min(float(growth_rate), 30.0))

    # ─── 1. Valoración por Múltiplos (60%) ───
    fv_multiple = eps * target_pe

    # ─── 2. Valoración de Graham (40%) ───
    # Fórmula: Valor = (EPS * (8.5 + 2g) * 4.4) / Y
    fv_graham = (eps * (8.5 + 2 * growth_rate) * 4.4) / bond_yield
    fv_graham = max(fv_graham, eps * 4.0)  # Piso: nunca menos que ~4x EPS

    fv_final = (fv_multiple * MULTIPLE_WEIGHT) + (fv_graham * GRAHAM_WEIGHT)

    if fv_final <= 0:
        return _error_result("FV <= 0", current_price)

    # ─── Cálculo del Margen de Seguridad ───
    margin_of_safety = (fv_final - current_price) / fv_final

    # Clamp -0.0
    if abs(margin_of_safety) < 0.0001:
        margin_of_safety = 0.0

    return {
        "fv_graham": round(fv_graham, 2),
        "fv_multiple": round(fv_multiple, 2),
        "fv_final": round(fv_final, 2),
        "margin_of_safety": round(margin_of_safety, 4),
        "is_buy": margin_of_safety >= 0.30,
        "method": "Graham+Multiples",
        "inputs": {
            "eps": eps,
            "target_pe": target_pe,
            "growth_rate": growth_rate,
            "current_price": current_price,
            "bond_yield": bond_yield
        }
    }

def _calculate_etf_fair_value(ticker: str, current_price: float) -> dict:
    """Para ETFs, el fair value es el NAV. No se valora por EPS."""
    try:
        info = yf.Ticker(ticker).info
        nav = info.get('navPrice')

        # Si no hay NAV, usar precio actual
        if nav is None or nav <= 0:
            nav = current_price if current_price > 0 else 0.0

        # MOS para ETF = descuento/premium al NAV
        if nav > 0 and current_price > 0:
            margin_of_safety = (nav - current_price) / nav
        else:
            margin_of_safety = 0.0

        # Clamp -0.0
        if abs(margin_of_safety) < 0.0001:
            margin_of_safety = 0.0

        return {
            "fv_graham": round(nav, 2),
            "fv_multiple": round(nav, 2),
            "fv_final": round(nav, 2),
            "margin_of_safety": round(margin_of_safety, 4),
            "is_buy": margin_of_safety >= 0.05,  # Comprar ETF solo si descuento > 5% al NAV
            "method": "ETF_NAV",
            "nav": round(nav, 2),
            "premium_discount": round((current_price - nav) / nav * 100, 2) if nav > 0 else 0.0,
            "inputs": {"ticker": ticker, "current_price": current_price, "nav": nav}
        }
    except Exception as e:
        # Fallback: precio actual, MOS = 0
        return {
            "fv_graham": round(current_price, 2),
            "fv_multiple": round(current_price, 2),
            "fv_final": round(current_price, 2),
            "margin_of_safety": 0.0,
            "is_buy": False,
            "method": "ETF_NAV_FALLBACK",
            "nav": round(current_price, 2),
            "premium_discount": 0.0,
            "error": str(e),
            "inputs": {"ticker": ticker, "current_price": current_price}
        }

def _error_result(reason: str, current_price: float = 0.0) -> dict:
    """Resultado de error con trazabilidad."""
    return {
        "fv_graham": 0.0,
        "fv_multiple": 0.0,
        "fv_final": 0.0,
        "margin_of_safety": 0.0,
        "is_buy": False,
        "method": "ERROR",
        "error_reason": reason,
        "inputs": {"current_price": current_price}
    }