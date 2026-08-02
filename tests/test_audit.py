import pytest
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from modules.db import Base, LedgerEntry
from modules.ledger import LedgerManager
from modules.audit import LedgerAuditor

@pytest.fixture
def mock_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    
    # Override el motor en el modulo audit para este test
    import modules.audit
    modules.audit.engine = engine
    
    yield session
    session.close()

def test_valid_chain(mock_db_session):
    ledger = LedgerManager(mock_db_session)
    
    # Transacción 1
    ledger.record_deposit(datetime.now(), 10000, memo="Init")
    mock_db_session.commit()
    
    # Transacción 2
    ledger.record_buy(datetime.now(), "AAPL", 10, 150, 1.0, memo="Buy")
    mock_db_session.commit()
    
    report = LedgerAuditor.verify_chain()
    
    assert report["status"] == "OK"
    assert report["valid_entries"] == 3 # 1 deposit, 2 legs for buy (position, commission)

def test_corrupted_chain_altered_amount(mock_db_session):
    ledger = LedgerManager(mock_db_session)
    ledger.record_deposit(datetime.now(), 10000, memo="Init")
    mock_db_session.commit()
    
    # Hackers atacan la base de datos y cambian el balance directo
    entry = mock_db_session.query(LedgerEntry).first()
    entry.amount = 9999999  # Se vuelve rico
    mock_db_session.commit()
    
    report = LedgerAuditor.verify_chain()
    
    assert report["status"] == "CORRUPTED"
    assert "Firma digital inválida" in report["message"]
