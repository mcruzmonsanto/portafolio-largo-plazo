import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date
from sqlalchemy.orm import Session
from modules.db import engine, Position, WatchlistItem
from modules.quant_engine import fetch_quant_data
from modules.signal_engine import BayesianSignal
from modules.alerts import AlertSystem
from app import calc_mos

def run_daily_cron():
    alert_sys = AlertSystem()
    print("Iniciando Daily Scanner Cron...")

    # 1. Analizar el Portafolio Actual
    with Session(engine) as session:
        positions = session.query(Position).all()
        tickers = [p.ticker for p in positions]
        
    if tickers:
        df_port = fetch_quant_data(tickers)
        if not df_port.empty:
            df_port['margin_of_safety'] = df_port.apply(calc_mos, axis=1)
            signal_engine = BayesianSignal(payoff_ratio=3.0)
            scores = df_port.apply(lambda r: signal_engine.generate_signal(r.get('composite_z', 0), r.get('margin_of_safety', 0)), axis=1)
            import pandas as pd
            scores_df = pd.DataFrame(list(scores))
            df_port = pd.concat([df_port, scores_df], axis=1)
            
            # Buscar degradaciones graves (NO COMPRAR o baja probabilidad)
            bad_assets = df_port[df_port['Signal'] == 'NO COMPRAR']
            if not bad_assets.empty:
                msg = ""
                for _, row in bad_assets.iterrows():
                    msg += f"⚠️ {row['ticker']} - Prob. Éxito: {row['prob_success']:.1%} - Z-Score: {row['composite_z']:.2f}\n"
                
                alert_sys.send_alert("🔴 Alerta Portafolio: Degradación de Calidad", 
                                   "Los siguientes activos en tu inventario presentan fundamentos deteriorados:\n\n" + msg)

    # 2. Analizar Watchlist por oportunidades doradas
    with Session(engine) as session:
        w_items = session.query(WatchlistItem).all()
        w_tickers = [w.ticker for w in w_items]
        
    if w_tickers:
        df_watch = fetch_quant_data(w_tickers)
        if not df_watch.empty:
            df_watch['margin_of_safety'] = df_watch.apply(calc_mos, axis=1)
            signal_engine = BayesianSignal(payoff_ratio=3.0)
            scores = df_watch.apply(lambda r: signal_engine.generate_signal(r.get('composite_z', 0), r.get('margin_of_safety', 0)), axis=1)
            import pandas as pd
            scores_df = pd.DataFrame(list(scores))
            df_watch = pd.concat([df_watch, scores_df], axis=1)
            
            good_assets = df_watch[df_watch['Signal'] == 'COMPRA FUERTE']
            if not good_assets.empty:
                msg = ""
                for _, row in good_assets.iterrows():
                    msg += f"🔥 {row['ticker']} - Prob. Éxito: {row['prob_success']:.1%} - Kelly Tgt: {row['kelly_fraction']:.1%}\n"
                
                alert_sys.send_alert("🟢 Oportunidad en Radar", 
                                   "Los siguientes activos en vigilancia han alcanzado métricas de Compra Fuerte:\n\n" + msg)
                                   
    print("Daily Scanner Cron finalizado.")

if __name__ == "__main__":
    run_daily_cron()
