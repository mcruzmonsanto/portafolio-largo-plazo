import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.data_quality import DataQualityMonitor, DataQualityFlag

def test_data_quality_sentinel_mock():
    monitor = DataQualityMonitor()
    now = datetime.now()
    
    # EPS nulo
    dp = monitor.assess('AAPL', 'eps', None, now)
    assert dp.flag == DataQualityFlag.MOCK
    
    # PE imposible (>500)
    dp2 = monitor.assess('AAPL', 'pe', 1000, now)
    assert dp2.flag == DataQualityFlag.MOCK
    
    # Dato faltante string vacío
    dp3 = monitor.assess('AAPL', 'price', "", now)
    assert dp3.flag == DataQualityFlag.MISSING

def test_data_quality_freshness():
    monitor = DataQualityMonitor()
    now = datetime.now()
    
    # Fresh (Hace 5 mins)
    fetch_time_fresh = now - timedelta(minutes=5)
    dp_fresh = monitor.assess('AAPL', 'eps', 5.5, fetch_time_fresh)
    assert dp_fresh.flag == DataQualityFlag.FRESH
    assert dp_fresh.is_reliable == True
    
    # Outdated (Hace 25 horas)
    fetch_time_outdated = now - timedelta(hours=25)
    dp_outdated = monitor.assess('AAPL', 'eps', 5.5, fetch_time_outdated)
    assert dp_outdated.flag == DataQualityFlag.OUTDATED
    assert dp_outdated.is_reliable == False
