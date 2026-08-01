import os
from datetime import datetime
from sqlalchemy.orm import Session
from modules.db import engine, Position, Transaction, CashFlow, init_db

def seed_data():
    init_db()
    
    with Session(engine) as session:
        # 1. Limpiar todas las tablas para evitar duplicados en la siembra
        session.query(Position).delete()
        session.query(Transaction).delete()
        session.query(CashFlow).delete()
        
        # 2. Insertar Posiciones Abiertas Exactas
        posiciones = [
            Position(ticker="AMZN", quantity=1.0, average_cost=234.21, fair_value_graham=210.0, fair_value_multiple=250.0, conviction_score=5),
            Position(ticker="AVGO", quantity=1.0, average_cost=385.69, fair_value_graham=350.0, fair_value_multiple=400.0, conviction_score=5),
            Position(ticker="GOOGL", quantity=1.0, average_cost=332.72, fair_value_graham=310.0, fair_value_multiple=350.0, conviction_score=4),
            Position(ticker="META", quantity=2.0, average_cost=591.58, fair_value_graham=550.0, fair_value_multiple=620.0, conviction_score=5),
            Position(ticker="MSFT", quantity=1.0, average_cost=402.74, fair_value_graham=380.0, fair_value_multiple=430.0, conviction_score=5),
            Position(ticker="NVDA", quantity=2.0, average_cost=204.67, fair_value_graham=180.0, fair_value_multiple=220.0, conviction_score=5),
            Position(ticker="PLTR", quantity=1.0, average_cost=116.25, fair_value_graham=95.0, fair_value_multiple=125.0, conviction_score=4),
            Position(ticker="QQQM", quantity=3.0, average_cost=294.50, fair_value_graham=280.0, fair_value_multiple=310.0, conviction_score=4),
            Position(ticker="SMH", quantity=2.0, average_cost=594.39, fair_value_graham=550.0, fair_value_multiple=620.0, conviction_score=4),
            Position(ticker="SPMO", quantity=4.0, average_cost=150.46, fair_value_graham=140.0, fair_value_multiple=165.0, conviction_score=4)
        ]
        session.add_all(posiciones)
        
        # 3. Transacciones en Efectivo (Aportes, Retiros, Dividendos, Impuestos y P/L Realizado)
        efectivo_data = [
            # Aportes y Retiros (Wires)
            ("2026-05-11", "DEPOSIT", 1480.00, "CASH RECEIVED WIRE"),
            ("2026-06-02", "DEPOSIT", 2180.00, "CASH RECEIVED WIRE"),
            ("2026-07-06", "DEPOSIT", 2540.00, "CASH RECEIVED WIRE"),
            ("2026-07-13", "WITHDRAW", -1000.00, "JNL TO 12069993"),
            ("2026-07-29", "DEPOSIT", 1480.00, "CASH RECEIVED WIRE"),
            
            # Dividendos e Impuestos
            ("2026-06-25", "DIVIDEND", 1.05, "FACEBOOK INC 2 (Dividendo)"),
            ("2026-06-25", "WITHDRAW", -0.32, "NRA WITHHOLD: DIVIDEND"),
            ("2026-06-26", "DIVIDEND", 1.06, "INVESCO EXCH TR 3 (Dividendo)"),
            ("2026-06-26", "WITHDRAW", -0.32, "NRA WITHHOLD: DIVIDEND"),
            ("2026-07-02", "DIVIDEND", 0.07, "FPL Revenue"),
            ("2026-07-02", "DIVIDEND", 0.07, "FPL INTEREST CR"),
            ("2026-07-02", "WITHDRAW", -0.02, "NRA WITHHOLDING"),
            ("2026-07-26", "DIVIDEND", 0.02, "07/26 ADJ NRA WH TAX"),
            
            # Ajuste por trades históricos cerrados en TradeStation (V, IBIT, WEN) 
            # para que la liquidez cuadre perfectamente con la plataforma.
            ("2026-06-29", "DEPOSIT", 9.96, "Realized P/L Neto Histórico")
        ]
        
        for fecha_str, accion, monto, nota in efectivo_data:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            
            # A. Registro en la Bitácora de Transacciones
            tx = Transaction(
                date=fecha, 
                ticker="Efectivo", 
                action=accion, 
                quantity=1.0,
                price=abs(monto),  # El precio en la bitácora siempre es positivo
                reason=nota
            )
            session.add(tx)
            
            # B. Registro en el Flujo de Caja para el Dashboard
            cf = CashFlow(
                date=fecha, 
                amount=monto, # Aquí sí respetamos el signo para sumar/restar
                type=accion
            )
            session.add(cf)
            
        session.commit()
        print("[OK] Base de datos sembrada con historial completo.")
        print("[INFO] Posiciones: 10 | Flujos de Efectivo: 14 registrados.")

if __name__ == "__main__":
    seed_data()