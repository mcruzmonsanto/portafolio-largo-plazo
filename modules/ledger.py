import uuid
from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from modules.db import LedgerEntry
from modules.audit import LedgerAuditor

class AccountType(Enum):
    ASSET_CASH = "ASSET:CASH"
    ASSET_POSITION = "ASSET:POSITION"
    INCOME_REALIZED_PNL = "INCOME:REALIZED_PNL"
    EXPENSE_COMMISSION = "EXPENSE:COMMISSION"
    EQUITY_NET_WORTH = "EQUITY:NET_WORTH"
    EQUITY_DEPOSIT = "EQUITY:DEPOSIT"

class LedgerManager:
    def __init__(self, session: Session):
        self.session = session
        
    def _create_entry(self, date: datetime, tx_id: str, debit: str, credit: str, amount: float, ticker: str = None, memo: str = ""):
        # Recuperar el hash del bloque anterior (la última fila insertada en la DB)
        last_entry = self.session.query(LedgerEntry).order_by(desc(LedgerEntry.id)).first()
        prev_hash = last_entry.entry_hash if last_entry and last_entry.entry_hash else "GENESIS"
        
        # Generar firma para esta transacción
        entry_data = {
            'date': date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date),
            'transaction_id': tx_id,
            'debit_account': debit,
            'credit_account': credit,
            'amount': amount,
            'ticker': ticker if ticker else '',
            'previous_hash': prev_hash
        }
        
        current_hash = LedgerAuditor.generate_hash(entry_data)
        
        entry = LedgerEntry(
            date=date,
            transaction_id=tx_id,
            debit_account=debit,
            credit_account=credit,
            amount=amount,
            ticker=ticker if ticker else '',
            memo=memo,
            previous_hash=prev_hash,
            entry_hash=current_hash
        )
        self.session.add(entry)
        self.session.flush() # Obliga a generar el ID para el siguiente bloque en la misma transacción
        
    def record_deposit(self, date: datetime, amount: float, memo: str = "Deposit"):
        """ DR ASSET:CASH | CR EQUITY:DEPOSIT """
        tx_id = str(uuid.uuid4())
        self._create_entry(date, tx_id, AccountType.ASSET_CASH.value, AccountType.EQUITY_DEPOSIT.value, amount, memo=memo)

    def record_withdrawal(self, date: datetime, amount: float, memo: str = "Withdrawal"):
        """ DR EQUITY:DEPOSIT | CR ASSET:CASH """
        tx_id = str(uuid.uuid4())
        self._create_entry(date, tx_id, AccountType.EQUITY_DEPOSIT.value, AccountType.ASSET_CASH.value, amount, memo=memo)

    def record_buy(self, date: datetime, ticker: str, quantity: float, price: float, commission: float = 0.0, memo: str = ""):
        """ 
        DR ASSET:POSITION:TICKER (Value)
        DR EXPENSE:COMMISSION (Commission)
        CR ASSET:CASH (Total)
        """
        tx_id = str(uuid.uuid4())
        value = quantity * price
        
        # Position Leg
        self._create_entry(date, tx_id, f"{AccountType.ASSET_POSITION.value}:{ticker}", AccountType.ASSET_CASH.value, value, ticker=ticker, memo=f"Buy {quantity} @ {price}")
        
        # Commission Leg
        if commission > 0:
            self._create_entry(date, tx_id, AccountType.EXPENSE_COMMISSION.value, AccountType.ASSET_CASH.value, commission, ticker=ticker, memo="Commission")

    def record_sell(self, date: datetime, ticker: str, quantity: float, price: float, cost_basis_price: float, commission: float = 0.0, memo: str = ""):
        """
        DR ASSET:CASH (Gross proceeds)
        CR ASSET:POSITION:TICKER (Original Cost)
        CR/DR INCOME:REALIZED_PNL (Gain/Loss)
        
        DR EXPENSE:COMMISSION
        CR ASSET:CASH
        """
        tx_id = str(uuid.uuid4())
        proceeds = quantity * price
        cost = quantity * cost_basis_price
        pnl = proceeds - cost
        
        if pnl >= 0:
            self._create_entry(date, tx_id, AccountType.ASSET_CASH.value, f"{AccountType.ASSET_POSITION.value}:{ticker}", cost, ticker=ticker, memo=f"Sell Cost Basis")
            if pnl > 0:
                self._create_entry(date, tx_id, AccountType.ASSET_CASH.value, AccountType.INCOME_REALIZED_PNL.value, pnl, ticker=ticker, memo=f"Realized Gain")
        else:
            loss_abs = abs(pnl)
            self._create_entry(date, tx_id, AccountType.ASSET_CASH.value, f"{AccountType.ASSET_POSITION.value}:{ticker}", proceeds, ticker=ticker, memo=f"Sell Proceeds")
            self._create_entry(date, tx_id, AccountType.INCOME_REALIZED_PNL.value, f"{AccountType.ASSET_POSITION.value}:{ticker}", loss_abs, ticker=ticker, memo=f"Realized Loss")
            
        if commission > 0:
            self._create_entry(date, tx_id, AccountType.EXPENSE_COMMISSION.value, AccountType.ASSET_CASH.value, commission, ticker=ticker, memo="Commission")

    def get_cash_balance(self) -> float:
        """ Returns the net balance of ASSET:CASH """
        debits = sum(e.amount for e in self.session.query(LedgerEntry).filter(LedgerEntry.debit_account == AccountType.ASSET_CASH.value).all())
        credits = sum(e.amount for e in self.session.query(LedgerEntry).filter(LedgerEntry.credit_account == AccountType.ASSET_CASH.value).all())
        return debits - credits
