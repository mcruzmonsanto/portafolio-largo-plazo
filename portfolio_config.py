import os
from pathlib import Path

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "portafolio.db"

# Parámetros del Portafolio y Riesgo
MAX_STOCK_WEIGHT = 0.10          # 10% máximo por acción individual
MAX_ETF_WEIGHT = 0.60            # 60% máximo por ETF
MIN_CASH_TARGET = 0.10           # 10% de efectivo libre mínimo
MARGIN_OF_SAFETY_THRESHOLD = 0.30  # 30% descuento mínimo requerido para compra
GRAHAM_WEIGHT = 0.40             # 40% peso al modelo de Benjamin Graham
MULTIPLE_WEIGHT = 0.60           # 60% peso a la valoración por múltiplos

# Credenciales y APIs (Capa 1)
# Recomendado: setear como variables de entorno reales en producción
POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY', 'mock_polygon_key')
ALPHAVANTAGE_API_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', 'mock_alpha_key')