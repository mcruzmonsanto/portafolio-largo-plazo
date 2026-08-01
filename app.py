import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from sqlalchemy.orm import Session
import plotly.express as px
import plotly.graph_objects as go

from modules.db import engine, Position, CashFlow, Transaction, PortfolioSnapshot, WatchlistItem, LedgerEntry
from modules.ledger import LedgerManager
from modules.quant_engine import fetch_quant_data
from modules.signal_engine import BayesianSignal
from modules.valuation import calculate_fair_value
from modules.scanner import AutoScanner, UNIVERSES
from modules.risk_manager import RiskManager
from portfolio_config import MAX_STOCK_WEIGHT, MAX_ETF_WEIGHT

st.set_page_config(page_title="Terminal Cuantitativo LP", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# --- REGLAS DURAS DEL PORTAFOLIO (INSTITUCIONALES) ---
DEFAULT_QUALITY_SCORE = 85
KNOWN_ETFS = ['SPY', 'VOO', 'QQQ', 'QQQM', 'SMH', 'SPMO', 'DIA', 'IWM', 'VTI', 'VT']

# Cálculo REAL del Margin of Safety global para evitar NameError
def calc_mos(row):
    eps = row.get('eps') or 0
    growth = row.get('growth') or 0.05
    price = row.get('current_price') or 0
    if eps and eps > 0 and price > 0:
        val = calculate_fair_value(eps, 15, growth * 100, price)
        return val['margin_of_safety']
    return -1.0

@st.cache_data(ttl=3600)
def get_market_regime():
    return RiskManager().detect_market_regime()

regime_data = get_market_regime()
dynamic_min_cash = regime_data['cash_target']
risk_multiplier = regime_data['risk_multiplier']

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🛡️ Reglas de Riesgo Activas")
    st.info(f"🔹 Máx. por Acción: {MAX_STOCK_WEIGHT*100}%\n\n🔹 Máx. Total ETFs: {MAX_ETF_WEIGHT*100}%\n\n🔹 Efectivo Mínimo: {dynamic_min_cash*100}%")
    
    st.markdown("---")
    st.subheader("🌐 Régimen Macro")
    color = "🟢" if "Bull" in regime_data['regime'] else ("🟡" if "Correction" in regime_data['regime'] else "🔴")
    st.markdown(f"**Estado:** {color} {regime_data['regime']}")
    st.markdown(f"**SPY:** ${regime_data['spy_price']:.2f} (SMA200: ${regime_data['spy_sma200']:.2f})")
    st.markdown(f"**VIX:** {regime_data['vix']:.2f}")
    st.markdown(f"**Apetito de Riesgo:** {risk_multiplier}x")
    
    st.markdown("---")
    st.info("📸 El Snapshot histórico se guarda automáticamente una vez al día.")

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60)
def load_positions():
    with engine.connect() as conn:
        return pd.read_sql("SELECT * FROM positions", conn)

@st.cache_data(ttl=60)
def load_cash_flows():
    with engine.connect() as conn:
        return pd.read_sql("SELECT * FROM cash_flows", conn)

@st.cache_data(ttl=60)
def load_transactions():
    with engine.connect() as conn:
        return pd.read_sql("SELECT * FROM transactions", conn)

@st.cache_data(ttl=60)
def load_snapshots():
    with engine.connect() as conn:
        return pd.read_sql("SELECT * FROM portfolio_history ORDER BY date ASC", conn)

@st.cache_data(ttl=60)
def load_watchlist():
    with engine.connect() as conn:
        return pd.read_sql("SELECT * FROM watchlist", conn)

st.title("🏛️ Terminal Cuantitativo Institucional")
st.markdown("---")

df_pos = load_positions()
df_cash = load_cash_flows()
df_tx = load_transactions()
df_snap = load_snapshots()
df_watch = load_watchlist()

# --- CÁLCULO DE LIQUIDEZ Y VALORACIÓN BÁSICA ---
with Session(engine) as session:
    lm = LedgerManager(session)
    total_cash = lm.get_cash_balance()
total_cost_basis = (df_pos['quantity'] * df_pos['average_cost']).sum() if not df_pos.empty else 0.0

total_market_value = 0.0
total_unrealized_pl = 0.0
portfolio_net_worth = total_cash

if portfolio_net_worth <= 0:
    st.error("⚠️ El Net Worth calculado es cero o negativo. Revisa tus movimientos de efectivo.")
    portfolio_net_worth = 0.01

df_enriched = pd.DataFrame()

if not df_pos.empty:
    with st.spinner("Sincronizando mercado y cuantificando riesgo..."):
        tickers = df_pos['ticker'].tolist()
        df_quant = fetch_quant_data(tickers)
        
        if not df_quant.empty:
            df_enriched = pd.merge(df_pos, df_quant, on='ticker', how='left')
            df_enriched['current_price'] = df_enriched['current_price'].replace(0, pd.NA)
            df_enriched['current_price'] = df_enriched['current_price'].fillna(df_enriched['average_cost'])
            
            df_enriched['market_value'] = df_enriched['quantity'] * df_enriched['current_price']
            df_enriched['cost_basis'] = df_enriched['quantity'] * df_enriched['average_cost']
            df_enriched['unrealized_pl'] = df_enriched['market_value'] - df_enriched['cost_basis']
            df_enriched['unrealized_pl_pct'] = (df_enriched['unrealized_pl'] / df_enriched['cost_basis']) * 100
            
            # Clasificación de Activos
            df_enriched['asset_type'] = df_enriched['ticker'].apply(lambda x: 'ETF' if x in KNOWN_ETFS else 'Stock')
            
            df_enriched['margin_of_safety'] = df_enriched.apply(calc_mos, axis=1)
            
            # Scores con gestión de riesgo macro
            signal_engine = BayesianSignal(payoff_ratio=3.0, risk_multiplier=risk_multiplier)
            def _apply_signal(row):
                return signal_engine.generate_signal(row.get('composite_z', 0), row.get('margin_of_safety', 0))
                
            scores = df_enriched.apply(_apply_signal, axis=1)
            scores_df = pd.DataFrame(list(scores))
            df_enriched = pd.concat([df_enriched, scores_df], axis=1)
            
            total_market_value = df_enriched['market_value'].sum()
            total_unrealized_pl = df_enriched['unrealized_pl'].sum()
            portfolio_net_worth = total_market_value + total_cash
            
            df_enriched['weight'] = df_enriched['market_value'] / portfolio_net_worth if portfolio_net_worth > 0 else 0

# --- LÓGICA DE GUARDADO DE SNAPSHOT AUTOMÁTICO ---
try:
    with Session(engine) as session:
        today = date.today()
        exist = session.query(PortfolioSnapshot).filter_by(date=today).first()
        if not exist and portfolio_net_worth > 0:
            snap = PortfolioSnapshot(
                date=today, 
                total_value=float(portfolio_net_worth), 
                cash=float(total_cash), 
                unrealized_pl=float(total_unrealized_pl)
            )
            session.add(snap)
            session.commit()
except Exception as e:
    pass 

# --- DASHBOARD DE MÉTRICAS VISUALES ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Net Worth", f"${portfolio_net_worth:,.2f}")
c2.metric("Liquidez (Cash)", f"${total_cash:,.2f}", delta=f"{(total_cash/portfolio_net_worth)*100:.1f}% del total" if portfolio_net_worth>0 else "")
c3.metric("P/L Abierto", f"${total_unrealized_pl:,.2f}", delta=f"{(total_unrealized_pl/total_cost_basis*100):.2f}%" if total_cost_basis > 0 else "0.00%")
beta_val = (df_enriched['beta'] * df_enriched['weight']).sum() if not df_enriched.empty else 0.0
c4.metric("Riesgo Beta Portafolio", f"{beta_val:.2f}", delta="Mercado = 1.0", delta_color="off")

st.markdown("---")

tab_dash, tab_watch, tab_scan, tab_reb, tab_esc, tab_tx = st.tabs([
    "📊 Resumen Visual", "🎯 Radar Watchlist", "📡 Auto-Scanner", "⚖️ Rebalanceador", "🌪️ Riesgo Histórico", "⚙️ Bitácora"
])

with tab_dash:
    col_chart1, col_chart2 = st.columns([1, 2])
    
    with col_chart1:
        st.subheader("Asset Allocation")
        if portfolio_net_worth > 0:
            total_stocks = df_enriched[df_enriched['asset_type'] == 'Stock']['market_value'].sum() if not df_enriched.empty else 0
            total_etfs = df_enriched[df_enriched['asset_type'] == 'ETF']['market_value'].sum() if not df_enriched.empty else 0
            
            fig = px.pie(
                names=['Efectivo', 'Acciones Individuales', 'ETFs'],
                values=[total_cash, total_stocks, total_etfs],
                hole=0.4,
                color_discrete_sequence=['#2ecc71', '#3498db', '#9b59b6']
            )
            fig.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=300, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
            
            # Alertas visuales de reglas
            if total_cash / portfolio_net_worth < dynamic_min_cash:
                st.error(f"⚠️ Alerta: Efectivo por debajo del {dynamic_min_cash*100:.1f}% mínimo sugerido por el régimen actual.")
            if total_etfs / portfolio_net_worth > MAX_ETF_WEIGHT:
                st.warning(f"⚠️ Alerta: Exposición a ETFs superior al límite del {MAX_ETF_WEIGHT*100:.1f}%.")
        else:
            st.info("Portafolio vacío.")
            
    with col_chart2:
        st.subheader("Inventario Consolidado")
        if not df_enriched.empty:
            disp_cols = ['ticker', 'current_price', 'market_value', 'weight', 'unrealized_pl_pct', 'prob_success', 'Signal']
            
            def color_signal(val):
                color = 'green' if 'COMPRA' in str(val) else 'red' if 'NO COMPRAR' in str(val) else 'gray'
                return f'color: {color}; font-weight: bold;'

            st.dataframe(
                df_enriched[disp_cols].style.map(color_signal, subset=['Signal']),
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "ticker": "Ticker",
                    "current_price": st.column_config.NumberColumn("Precio", format="$%.2f"),
                    "market_value": st.column_config.NumberColumn("Valor Mercado", format="$%.2f"),
                    "weight": st.column_config.ProgressColumn("Peso %", format="%.2f", min_value=0, max_value=MAX_STOCK_WEIGHT*1.5),
                    "unrealized_pl_pct": st.column_config.NumberColumn("Retorno %", format="%.2f%%"),
                    "prob_success": st.column_config.NumberColumn("Prob. Éxito", format="%.2f"),
                    "Signal": "Señal"
                },
                height=350
            )

with tab_watch:
    st.subheader("🎯 Radar Inteligente (Watchlist)")
    st.markdown("Monitorea oportunidades y calcula la entrada perfecta de acuerdo a tus límites de riesgo.")
    
    col_w1, col_w2 = st.columns([1, 4])
    with col_w1:
        with st.form("add_watch_form"):
            new_wticker = st.text_input("Agregar Ticker").upper()
            w_notes = st.text_input("Tesis breve")
            submitted_w = st.form_submit_button("Vigilar")
            
            if submitted_w and new_wticker:
                try:
                    with Session(engine) as session:
                        if not session.query(WatchlistItem).filter_by(ticker=new_wticker).first():
                            session.add(WatchlistItem(ticker=new_wticker, added_date=date.today(), notes=w_notes))
                            session.commit()
                            st.success(f"{new_wticker} agregado.")
                            load_watchlist.clear()
                            st.rerun()
                except Exception as e:
                    st.error(f"Error agregando a watchlist: {e}")
                    
        with st.form("del_watch_form"):
            del_wticker = st.selectbox("Eliminar Ticker", df_watch['ticker'].tolist() if not df_watch.empty else ["Vacío"])
            del_w = st.form_submit_button("Quitar del Radar")
            if del_w and del_wticker != "Vacío":
                with Session(engine) as session:
                    wt = session.query(WatchlistItem).filter_by(ticker=del_wticker).first()
                    if wt:
                        session.delete(wt)
                        session.commit()
                        load_watchlist.clear()
                        st.rerun()

    with col_w2:
        if not df_watch.empty:
            w_tickers = df_watch['ticker'].tolist()
            with st.spinner("Analizando Radar..."):
                import math
                df_wq = fetch_quant_data(w_tickers)
                if not df_wq.empty:
                    df_wq['margin_of_safety'] = df_wq.apply(calc_mos, axis=1)
                    
                    signal_engine = BayesianSignal(payoff_ratio=3.0, risk_multiplier=risk_multiplier)
                    w_scores = df_wq.apply(lambda r: signal_engine.generate_signal(r.get('composite_z', 0), r.get('margin_of_safety', 0)), axis=1)
                    w_scores_df = pd.DataFrame(list(w_scores))
                    df_wq = pd.concat([df_wq, w_scores_df], axis=1)
                    
                    # Merge con notas de watchlist
                    df_wq = pd.merge(df_wq, df_watch, on='ticker', how='left')
                    
                    # Lógica de "Sugerencia de Compra"
                    def get_buy_suggestion(row):
                        if row['Signal'] not in ['COMPRA FUERTE', 'COMPRA']:
                            return "Mantenerse al margen"
                            
                        # Limite según tipo de activo
                        max_w = MAX_ETF_WEIGHT if row['ticker'] in KNOWN_ETFS else MAX_STOCK_WEIGHT
                        
                        # ¿Cuánto de este activo ya tenemos?
                        current_w = 0.0
                        if not df_enriched.empty and row['ticker'] in df_enriched['ticker'].values:
                            current_w = df_enriched[df_enriched['ticker'] == row['ticker']]['weight'].values[0]
                            
                        space_left_pct = max_w - current_w
                        if space_left_pct <= 0:
                            return "Posición al tope (Regla Riesgo)"
                            
                        # Efectivo disponible por encima del target mínimo
                        available_cash = total_cash - (portfolio_net_worth * dynamic_min_cash)
                        if available_cash <= 0:
                            return "No hay efectivo libre"
                            
                        max_usd_alloc = portfolio_net_worth * space_left_pct
                        invest_usd = min(max_usd_alloc, available_cash)
                        shares_to_buy = math.floor(invest_usd / row['current_price'])
                        if shares_to_buy < 1:
                            return "Capital Insuficiente"
                            
                        real_invest = shares_to_buy * row['current_price']
                        return f"Comprar {shares_to_buy} accs (~${real_invest:,.0f})"
                        
                    df_wq['Action_Plan'] = df_wq.apply(get_buy_suggestion, axis=1)
                    
                    # Calcular Upside % y Tiempo Estimado de forma vectorizada
                    df_wq['upside_pct'] = ((df_wq['target_price'] - df_wq['current_price']) / df_wq['current_price'] * 100).where(
                        df_wq['target_price'].notna() & df_wq['current_price'].notna() & (df_wq['current_price'] > 0), 0.0
                    )
                    
                    df_wq['time_to_target_months'] = ((df_wq['target_price'] - df_wq['current_price']) / df_wq['current_price'] / df_wq['volatility'].replace(0, pd.NA) * 12).where(
                        df_wq['target_price'].notna() & df_wq['current_price'].notna() & (df_wq['current_price'] > 0) & df_wq['volatility'].notna(), float('inf')
                    )
                    
                    # Convertir Market Cap a Billones (B) para que sea numérico y se pueda ordenar
                    df_wq['market_cap_billions'] = df_wq['market_cap'] / 1e9
                    
                    # Estilos visuales de la señal
                    def color_watchlist_signal(val):
                        if pd.isna(val): return ''
                        val_str = str(val)
                        if 'NO COMPRAR' in val_str or 'tope' in val_str or 'Insuficiente' in val_str:
                            return 'background-color: #3b1c1c; color: #e74c3c;'
                        elif 'COMPRA FUERTE' in val_str:
                            return 'background-color: #1e3d2f; color: #2ecc71; font-weight: bold;'
                        elif 'COMPRA' in val_str:
                            return 'background-color: #1a2f24; color: #2ecc71;'
                        elif 'ESPERAR' in val_str or 'Mantener' in val_str:
                            return 'background-color: #40320a; color: #f1c40f;'
                        return ''
                        
                    styled_df = df_wq[['ticker', 'current_price', 'target_price', 'upside_pct', 'time_to_target_months', 'market_cap_billions', 'beta', 'Signal', 'prob_success', 'kelly_fraction', 'Action_Plan', 'notes']].style.map(color_watchlist_signal, subset=['Signal', 'Action_Plan'])
                    
                    st.dataframe(
                        styled_df,
                        use_container_width=True, hide_index=True,
                        column_config={
                            "current_price": st.column_config.NumberColumn("Precio", format="$%.2f"),
                            "target_price": st.column_config.NumberColumn("Precio Obj.", format="$%.2f"),
                            "upside_pct": st.column_config.NumberColumn("Upside", format="%.2f%%"),
                            "time_to_target_months": st.column_config.NumberColumn("Tiempo Est. (Meses)", format="%.1f M"),
                            "market_cap_billions": st.column_config.NumberColumn("Market Cap (Billones)", format="$%.2f B"),
                            "beta": st.column_config.NumberColumn("Beta", format="%.2f"),
                            "prob_success": st.column_config.NumberColumn("Prob. Éxito", format="%.2f"),
                            "kelly_fraction": st.column_config.NumberColumn("Kelly Target", format="%.2%"),
                            "Action_Plan": "Plan de Acción Sugerido",
                            "notes": "Tesis"
                        }
                    )
        else:
            st.info("El Radar está vacío. Agrega acciones a la izquierda para que el sistema las evalúe.")

with tab_scan:
    st.subheader("📡 Auto-Scanner Institucional")
    st.markdown("Busca oportunidades de inversión en tiempo real sobre universos completos.")
    
    col_s1, col_s2 = st.columns([1, 4])
    with col_s1:
        st.write("Configuración")
        selected_universe = st.selectbox("Universo a Escanear", list(UNIVERSES.keys()))
        min_kelly_filter = st.slider("Min. Kelly %", min_value=0.01, max_value=0.20, value=0.05, step=0.01)
        run_scan = st.button("🚀 Ejecutar Escáner")
        
    with col_s2:
        if run_scan:
            with st.spinner(f"Escaneando {selected_universe}... esto puede tomar un momento."):
                scanner = AutoScanner()
                try:
                    df_opps = scanner.scan_universe(selected_universe, min_kelly=min_kelly_filter)
                    if df_opps.empty:
                        st.warning("No se encontraron oportunidades que cumplan los estrictos filtros de riesgo y margen de seguridad.")
                    else:
                        st.success(f"¡Se encontraron {len(df_opps)} oportunidades doradas!")
                        
                        # Formato visual
                        def color_scanner_signal(val):
                            if 'FUERTE' in str(val): return 'background-color: #1e3d2f; color: #2ecc71; font-weight: bold;'
                            return 'background-color: #1a2f24; color: #2ecc71;'
                            
                        styled_opps = df_opps[['ticker', 'current_price', 'composite_z', 'prob_success', 'kelly_fraction', 'Signal']].style.map(color_scanner_signal, subset=['Signal'])
                        
                        st.dataframe(
                            styled_opps,
                            use_container_width=True, hide_index=True,
                            column_config={
                                "current_price": st.column_config.NumberColumn("Precio", format="$%.2f"),
                                "composite_z": st.column_config.NumberColumn("Z-Score", format="%.2f"),
                                "prob_success": st.column_config.NumberColumn("Prob. Éxito", format="%.2f"),
                                "kelly_fraction": st.column_config.NumberColumn("Kelly Target", format="%.2%"),
                            }
                        )
                        
                        st.info("💡 Consejo: Copia los Tickers que te interesen y agrégalos manualmente al Radar Watchlist para seguimiento diario.")
                except Exception as e:
                    st.error(f"Error en escáner: {e}")

with tab_reb:
    st.subheader("⚖️ Rebalanceo de Portafolio Existente")
    if not df_enriched.empty:
        df_buy = df_enriched[['ticker', 'asset_type', 'prob_success', 'kelly_fraction', 'Signal', 'weight', 'market_value']].copy()
        
        def calc_target(row):
            limit = MAX_ETF_WEIGHT if row['asset_type'] == 'ETF' else MAX_STOCK_WEIGHT
            base_target = row.get('kelly_fraction', 0)
            return min(base_target, limit)
            
        df_buy['target_weight'] = df_buy.apply(calc_target, axis=1)
        
        # Ajuste global para respetar el cash
        total_target = df_buy['target_weight'].sum()
        max_investable = 1.0 - dynamic_min_cash
        if total_target > max_investable and total_target > 0:
            df_buy['target_weight'] = (df_buy['target_weight'] / total_target) * max_investable
        elif total_target == 0:
            df_buy['target_weight'] = 0.0
            
        df_buy['weight_delta'] = df_buy['target_weight'] - df_buy['weight']
        df_buy['Action'] = df_buy.apply(lambda r: "COMPRAR" if r['weight_delta'] > 0.01 else ("REDUCIR" if r['weight_delta'] < -0.01 else "MANTENER"), axis=1)
        
        st.dataframe(
            df_buy[['ticker', 'Signal', 'weight', 'target_weight', 'weight_delta', 'Action']],
            use_container_width=True, hide_index=True,
            column_config={
                "weight": st.column_config.NumberColumn("Peso Actual", format="%.2%"),
                "target_weight": st.column_config.NumberColumn("Peso Objetivo", format="%.2%"),
                "weight_delta": st.column_config.NumberColumn("Desviación", format="%.2%"),
            }
        )

with tab_esc:
    st.subheader("🌪️ Evolución y Riesgo")
    colA, colB = st.columns([2, 1])
    
    with colA:
        if not df_snap.empty:
            fig_hist = px.area(df_snap, x='date', y='total_value', title='Crecimiento de Capital (Net Worth)')
            fig_hist.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=300)
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("Sin histórico suficiente.")
            
    with colB:
        st.markdown(f"**Test de Estrés (Beta Ponderado: {beta_val:.2f})**")
        if not df_enriched.empty:
            val = portfolio_net_worth
            scenarios = [
                {"Escenario": "Shock Leve (-10%)", "Impacto (VaR)": -0.10 * beta_val * val, "Colchón Cash": total_cash},
                {"Escenario": "Bear Market (-25%)", "Impacto (VaR)": -0.25 * beta_val * val, "Colchón Cash": total_cash},
                {"Escenario": "Black Swan (-40%)", "Impacto (VaR)": -0.40 * beta_val * val, "Colchón Cash": total_cash},
            ]
            df_esc = pd.DataFrame(scenarios)
            st.dataframe(df_esc, hide_index=True, column_config={
                "Impacto (VaR)": st.column_config.NumberColumn(format="-$%.2f"),
                "Colchón Cash": st.column_config.NumberColumn(format="$%.2f")
            })

with tab_tx:
    st.subheader("⚙️ Registro y Bitácora de Transacciones")
    if "op_msg" in st.session_state:
        st.success(st.session_state["op_msg"])
        del st.session_state["op_msg"]
    if "op_err" in st.session_state:
        st.error(st.session_state["op_err"])
        del st.session_state["op_err"]

    instrumento = st.radio("Tipo de Movimiento", ["Acción", "Efectivo"], horizontal=True)

    with st.form("ops_form"):
        if instrumento == "Efectivo":
            col1, col2 = st.columns(2)
            with col1:
                op_date = st.date_input("Fecha")
                op_action = st.selectbox("Movimiento", ["DEPOSIT", "WITHDRAW", "DIVIDEND"])
            with col2:
                op_price = st.number_input("Monto (USD)", min_value=0.01, step=1.0, format="%.2f")
                op_reason = st.text_input("Nota")
            op_ticker = "Efectivo"
            op_qty = 1.0
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                op_date = st.date_input("Fecha")
                op_action = st.selectbox("Operación", ["BUY", "SELL"])
            with col2:
                op_ticker = st.text_input("Ticker").upper()
                op_qty = st.number_input("Cantidad", min_value=0.01, format="%.2f")
            with col3:
                op_price = st.number_input("Precio por Acción (USD)", min_value=0.01, format="%.2f")
                op_reason = st.text_input("Motivo")

        submit_op = st.form_submit_button("Registrar Transacción")

    if submit_op:
        try:
            with Session(engine) as session:
                if instrumento != "Efectivo" and not op_ticker:
                    st.session_state["op_err"] = "⚠️ Ingresa Ticker válido."
                    st.rerun()
                nueva_tx = Transaction(date=op_date, ticker=op_ticker, action=op_action, quantity=op_qty, price=op_price, reason=op_reason)
                session.add(nueva_tx)
                # Registrar en Ledger
                lm = LedgerManager(session)
                
                if instrumento == "Acción":
                    pos = session.query(Position).filter_by(ticker=op_ticker).first()
                    if op_action == "BUY":
                        lm.record_buy(op_date, op_ticker, op_qty, op_price, memo=op_reason)
                        if pos:
                            total_cost_prev = pos.quantity * pos.average_cost
                            new_total_cost = total_cost_prev + (op_qty * op_price)
                            pos.quantity += op_qty
                            pos.average_cost = new_total_cost / pos.quantity
                        else:
                            session.add(Position(ticker=op_ticker, quantity=op_qty, average_cost=op_price))
                    elif op_action == "SELL":
                        if not pos:
                            st.session_state["op_err"] = "Activo no en inventario."
                            st.rerun()
                        if op_qty > pos.quantity:
                            st.session_state["op_err"] = f"Solo posees {pos.quantity:.4f} unidades."
                            st.rerun()
                            
                        lm.record_sell(op_date, op_ticker, op_qty, op_price, pos.average_cost, memo=op_reason)
                        
                        pos.quantity -= op_qty
                        if pos.quantity <= 0:
                            session.delete(pos)
                elif instrumento == "Efectivo":
                    if op_action == "WITHDRAW":
                        lm.record_withdrawal(op_date, op_price, memo=op_reason)
                    elif op_action == "DEPOSIT":
                        lm.record_deposit(op_date, op_price, memo=op_reason)
                    elif op_action == "DIVIDEND":
                        import uuid
                        tx_id = str(uuid.uuid4())
                        lm._create_entry(op_date, tx_id, "ASSET:CASH", "INCOME:DIVIDEND", op_price, memo=op_reason)
                        
                    multiplier = -1 if op_action == "WITHDRAW" else 1
                    session.add(CashFlow(date=op_date, amount=op_price * multiplier, type=op_action))
                session.commit()
                load_positions.clear()
                load_cash_flows.clear()
                load_transactions.clear()
                st.session_state["op_msg"] = "✅ Operación registrada."
            st.rerun()
        except Exception as e:
            st.error(f"Error BD: {e}")

    st.divider()
    st.subheader("📜 Historial de Transacciones")
    if not df_tx.empty:
        df_tx_display = df_tx.sort_values(by='date', ascending=False)
        st.dataframe(df_tx_display[['id', 'date', 'ticker', 'action', 'quantity', 'price', 'reason']], use_container_width=True, hide_index=True)