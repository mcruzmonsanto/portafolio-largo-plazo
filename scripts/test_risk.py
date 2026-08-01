import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.risk_manager import RiskManager

rm = RiskManager()
regime = rm.detect_market_regime()
print(regime)
