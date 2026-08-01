import os
from pathlib import Path

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "portafolio.db"

# Parámetros del Portafolio y Riesgo
MAX_POSITION_WEIGHT = 0.15       # 15% peso máximo sugerido por posición
MARGIN_OF_SAFETY_THRESHOLD = 0.30  # 30% descuento mínimo requerido para compra
GRAHAM_WEIGHT = 0.40             # 40% peso al modelo de Benjamin Graham
MULTIPLE_WEIGHT = 0.60           # 60% peso a la valoración por múltiplos