import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from modules.db import engine, Base, Transaction, CashFlow, Position, init_db

def reset_and_seed():
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS transactions"))
        conn.execute(text("DROP TABLE IF EXISTS cash_flows"))
        conn.commit()
        
    init_db()
    
    cash_data = [
        ("2026-05-10", "DEPOSIT", 9.86, "Initial Cash Balance"),
        ("2026-05-11", "DEPOSIT", 1480.00, "CASH RECEIVED WIRE"),
        ("2026-06-02", "DEPOSIT", 2180.00, "CASH RECEIVED WIRE"),
        ("2026-06-04", "WITHDRAW", -50.00, "TradeStation Charges"),
        ("2026-06-04", "DEPOSIT", 50.00, "TradeStation Charges"),
        ("2026-06-25", "DIVIDEND", 1.05, "FACEBOOK INC 2"),
        ("2026-06-25", "WITHDRAW", -0.32, "NRA WITHHOLD: DIVIDEND"),
        ("2026-06-26", "DIVIDEND", 1.06, "INVESCO EXCH TR 3"),
        ("2026-06-26", "WITHDRAW", -0.32, "NRA WITHHOLD: DIVIDEND"),
        ("2026-07-02", "DIVIDEND", 0.07, "FPL Revenue"),
        ("2026-07-02", "DIVIDEND", 0.07, "FPL INTEREST CR"),
        ("2026-07-02", "WITHDRAW", -0.02, "NRA WITHHOLDING"),
        ("2026-07-06", "DEPOSIT", 2540.00, "CASH RECEIVED WIRE"),
        ("2026-07-09", "DEPOSIT", 50.00, "TradeStation Charges"),
        ("2026-07-09", "WITHDRAW", -50.00, "TradeStation Charges"),
        ("2026-07-13", "WITHDRAW", -1000.00, "JNL TO 12069993"),
        ("2026-07-27", "DIVIDEND", 0.02, "07/26 ADJ NRA WH TAX"),
        ("2026-07-29", "DEPOSIT", 1480.00, "CASH RECEIVED WIRE")
    ]
    
    tx_data = [
        ("2026-07-30", "AVGO", "BUY", 1.0, 385.69),
        ("2026-07-30", "GOOGL", "BUY", 1.0, 332.72),
        ("2026-07-28", "NVDA", "BUY", 1.0, 197.76),
        ("2026-07-13", "SMH", "BUY", 1.0, 591.34),
        ("2026-07-13", "SPMO", "BUY", 4.0, 150.46),
        ("2026-06-29", "WEN", "SELL", 1.0, 9.10),
        ("2026-06-29", "PLTR", "BUY", 1.0, 116.25),
        ("2026-06-29", "AMZN", "BUY", 1.0, 234.21),
        ("2026-06-24", "WEN", "BUY", 1.0, 9.05),
        ("2026-06-22", "IBIT", "SELL", 16.0, 35.84),
        ("2026-06-22", "NVDA", "BUY", 1.0, 211.58),
        ("2026-06-12", "IBIT", "BUY", 16.0, 35.88),
        ("2026-06-11", "META", "BUY", 1.0, 560.09),
        ("2026-06-11", "V", "SELL", 1.0, 320.53),
        ("2026-06-09", "MSFT", "BUY", 1.0, 402.74),
        ("2026-06-08", "SMH", "BUY", 1.0, 597.43),
        ("2026-06-04", "QQQM", "BUY", 3.0, 294.50),
        ("2026-06-04", "V", "BUY", 1.0, 320.22),
        ("2026-06-03", "META", "BUY", 1.0, 623.06)
    ]
    
    with Session(engine) as session:
        for date_str, type_str, amount, reason in cash_data:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            cf = CashFlow(date=dt, type=type_str, amount=amount)
            session.add(cf)
            
        for date_str, ticker, action, qty, price in tx_data:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            tx = Transaction(date=dt, ticker=ticker, action=action, quantity=qty, price=price, reason="TradeStation Sync")
            session.add(tx)
            
        session.commit()
        print("Migracion completada!")

if __name__ == "__main__":
    reset_and_seed()
