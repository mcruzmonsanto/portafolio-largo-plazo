import yfinance as yf
from portfolio_config import GRAHAM_WEIGHT, MULTIPLE_WEIGHT

def calculate_fair_value(eps: float, target_pe: float, growth_rate: float, current_price: float, bond_yield: float = 4.4) -> dict:
    """
    Calcula el Valor Intrínseco (Fair Value) combinando Graham y Múltiplos.
    """
    # Evitar valoraciones irreales si la empresa tiene pérdidas (EPS negativo)
    if eps <= 0:
        return {
            "fv_graham": 0.0,
            "fv_multiple": 0.0,
            "fv_final": 0.0,
            "margin_of_safety": 0.0,
            "is_buy": False
        }

    # 1. Valoración por Múltiplos (60%)
    fv_multiple = eps * target_pe

    # 2. Valoración de Graham (40%)
    # Fórmula: Valor = (EPS * (8.5 + 2g) * 4.4) / Y
    fv_graham = (eps * (8.5 + 2 * growth_rate) * 4.4) / bond_yield
    fv_graham = max(fv_graham, eps * 4.0) # piso: nunca menos que ~4x EPS, evita valores negativos o absurdos

    fv_final = (fv_multiple * MULTIPLE_WEIGHT) + (fv_graham * GRAHAM_WEIGHT)

    if fv_final <= 0:
        return {
            "fv_graham": round(fv_graham, 2),
            "fv_multiple": round(fv_multiple, 2),
            "fv_final": 0.0,
            "margin_of_safety": -1.0,
            "is_buy": False
        }

    # 4. Cálculo del Margen de Seguridad
    if current_price > 0 and fv_final > 0:
        if current_price > fv_final:
            # Sobrevalorado: MOS negativo (usamos current_price como base para no inflar % absurdos)
            margin_of_safety = (fv_final - current_price) / current_price
        else:
            # Subvalorado: MOS positivo
            margin_of_safety = (fv_final - current_price) / fv_final
    else:
        margin_of_safety = 0.0

    return {
        "fv_graham": round(fv_graham, 2),
        "fv_multiple": round(fv_multiple, 2),
        "fv_final": round(fv_final, 2),
        "margin_of_safety": margin_of_safety,
        "is_buy": margin_of_safety >= 0.30  # Usamos el 30% estricto de margen
    }

def calculate_fair_value_etf(ticker: str, current_price: float) -> dict:
    """
    Para ETFs, el 'fair value' es el NAV (Net Asset Value).
    No se valora por EPS, sino por el valor intrínseco de los holdings.
    """
    try:
        etf = yf.Ticker(ticker)
        info = etf.info
        
        nav = info.get('navPrice', current_price)
        premium = (current_price - nav) / nav if nav > 0 else 0
        
        # Para ETFs de índice amplio, el fair value ≈ NAV
        # El MOS es el descuento/premium: negativo = sobrevalorado
        mos = -premium  # Si premium es 2%, MOS = -2%
        
        return {
            "fv_graham": nav,
            "fv_multiple": nav,
            "fv_final": nav,
            "margin_of_safety": mos,
            "is_buy": mos >= 0.05,  # Comprar solo si hay descuento al NAV > 5%
            "nav": nav,
            "premium_discount": premium
        }
    except Exception:
        # Fallback: asumir fair value = precio actual (MOS = 0)
        return {
            "fv_graham": current_price,
            "fv_multiple": current_price,
            "fv_final": current_price,
            "margin_of_safety": 0.0,
            "is_buy": False,
            "nav": current_price,
            "premium_discount": 0.0
        }