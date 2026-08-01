from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

class DataQualityFlag(Enum):
    FRESH = "🟢"           # < 15 min
    STALE = "🟡"           # 15 min - 2 horas
    OUTDATED = "🟠"        # 2-24 horas
    MOCK = "🔴"            # Fallback/sintético
    MISSING = "⚫"         # No disponible

@dataclass
class DataPoint:
    value: float
    timestamp: datetime
    source: str
    flag: DataQualityFlag
    
    @property
    def is_reliable(self) -> bool:
        return self.flag in (DataQualityFlag.FRESH, DataQualityFlag.STALE)

class DataQualityMonitor:
    def __init__(self):
        self.quality_log = []  # Para auditoría
    
    def assess(self, ticker: str, field: str, raw_value, fetch_time: datetime) -> DataPoint:
        """Evalúa la calidad de cada dato individual"""
        
        # 1. Detección de valores sentinel
        if raw_value in (None, 0, 0.0, "N/A", ""):
            if field in ('eps', 'pe', 'roe', 'beta'):  # Fundamentales a menudo faltan
                return DataPoint(0.0, fetch_time, "yfinance", DataQualityFlag.MOCK)
            return DataPoint(0.0, fetch_time, "yfinance", DataQualityFlag.MISSING)
        
        try:
            val_float = float(raw_value)
        except (ValueError, TypeError):
            return DataPoint(0.0, fetch_time, "yfinance", DataQualityFlag.MISSING)

        # 2. Detección de valores imposibles
        if field == 'pe' and (val_float < 0 or val_float > 500):
            return DataPoint(val_float, fetch_time, "yfinance", DataQualityFlag.MOCK)
        if field == 'beta' and abs(val_float) > 5:
            return DataPoint(val_float, fetch_time, "yfinance", DataQualityFlag.MOCK)
        
        # 3. Freshness
        age = datetime.now() - fetch_time
        if age < timedelta(minutes=15):
            flag = DataQualityFlag.FRESH
        elif age < timedelta(hours=2):
            flag = DataQualityFlag.STALE
        else:
            flag = DataQualityFlag.OUTDATED
        
        return DataPoint(val_float, fetch_time, "yfinance", flag)
    
    def render_quality_badge(self, datapoint: DataPoint) -> str:
        """Devuelve HTML para badge en Streamlit"""
        return f"{datapoint.flag.value} {datapoint.source} · {datapoint.timestamp.strftime('%H:%M')}"
