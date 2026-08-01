import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from sqlalchemy.orm import Session
from modules.db import engine, Transaction, CashFlow, Position, LedgerEntry, Base
from modules.ledger import LedgerManager

def migrate():
    # Make sure new tables exist
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Check if already migrated
        if session.query(LedgerEntry).count() > 0:
            print("Ledger already populated. Skipping migration.")
            return

        print("Starting ledger migration...")
        lm = LedgerManager(session)

        # 1. Cash Flows (Deposits/Withdrawals)
        cash_flows = session.query(CashFlow).order_by(CashFlow.date).all()
        for cf in cash_flows:
            if cf.type == "DEPOSIT" or cf.amount > 0:
                lm.record_deposit(cf.date, abs(cf.amount), memo=f"Migrated {cf.type}")
            elif cf.type == "WITHDRAW" or cf.amount < 0:
                lm.record_withdrawal(cf.date, abs(cf.amount), memo=f"Migrated {cf.type}")
            elif cf.type == "DIVIDEND":
                # Divs are cash in, credit PNL
                tx_id = "migrated-" + str(cf.id)
                lm._create_entry(cf.date, tx_id, "ASSET:CASH", "INCOME:DIVIDEND", abs(cf.amount), memo="Migrated Dividend")
        
        # 2. Transactions (Buys/Sells)
        transactions = session.query(Transaction).order_by(Transaction.date).all()
        
        for tx in transactions:
            if tx.action == "BUY":
                lm.record_buy(tx.date, tx.ticker, tx.quantity, tx.price, memo="Migrated BUY")
            elif tx.action == "SELL":
                pos = session.query(Position).filter_by(ticker=tx.ticker).first()
                cost_basis = pos.average_cost if pos else tx.price
                lm.record_sell(tx.date, tx.ticker, tx.quantity, tx.price, cost_basis, memo="Migrated SELL")
                
        session.commit()
        print("Migration complete. Ledger balances updated.")

if __name__ == "__main__":
    migrate()
