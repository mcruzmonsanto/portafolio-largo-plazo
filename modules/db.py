import os
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Identity
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DB_PATH, DATA_DIR

# Asegurar que el directorio de la base de datos local exista
os.makedirs(DATA_DIR, exist_ok=True)

# --- LÓGICA DE CONEXIÓN DUAL (NUBE VS LOCAL) ---
try:
    # Intentamos leer el secreto de Supabase desde la configuración nativa de Streamlit
    DATABASE_URL = st.secrets["connections"]["supabase"]["url"]
    print("[CLOUD] Entorno detectado: Conectando a Supabase (PostgreSQL)")
except Exception:
    # Fallback a desarrollo local si no hay secrets.toml o falla la lectura
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    print("[LOCAL] Entorno detectado: Conectando a SQLite Local")

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

class Position(Base):
    __tablename__ = 'positions'
    ticker = Column(String, primary_key=True)
    quantity = Column(Float, default=0.0)
    average_cost = Column(Float, default=0.0)
    
    # Fundamentales y Valoración
    fair_value_graham = Column(Float, nullable=True)
    fair_value_multiple = Column(Float, nullable=True)
    conviction_score = Column(Integer, default=0)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    date = Column(Date, nullable=False)
    ticker = Column(String, nullable=False)
    action = Column(String, nullable=False)  # 'BUY' o 'SELL'
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    reason = Column(String, nullable=True)

class CashFlow(Base):
    __tablename__ = 'cash_flows'
    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)

class PortfolioSnapshot(Base):
    __tablename__ = 'portfolio_history'
    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    date = Column(Date, nullable=False, unique=True)
    total_value = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    unrealized_pl = Column(Float, nullable=False)

class WatchlistItem(Base):
    __tablename__ = 'watchlist'
    ticker = Column(String, primary_key=True)
    added_date = Column(Date, nullable=False)
    notes = Column(String, nullable=True)

def init_db():
    """Crea las tablas en la base de datos activa si no existen."""
    Base.metadata.create_all(engine)
    print("[OK] Tablas sincronizadas con la base de datos.")


if __name__ == "__main__":
    init_db()