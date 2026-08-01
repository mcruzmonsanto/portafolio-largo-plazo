import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy.orm import Session
from modules.db import engine, Position, CashFlow, Transaction, PortfolioSnapshot
from modules.market_data import fetch_live_data
from modules.valuation import calculate_fair_value
from modules.quant_engine import fetch_quant_data, calculate_scores

st.set_page_config(page_title="Terminal Cuantitativo LP", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# --- BARRA LATERAL (CONFIGURACIÓN INSTITUCIONAL) ---
with st.sidebar:
    st.header("⚙️ Parámetros de Riesgo")
    max_weight = st.slider("Peso Máximo por Posición", 5, 30, 15, format="%d%%") / 100
    target_cash = st.slider("Efectivo Objetivo", 0, 30, 10, format="%d%%") / 100
    default_pe = st.number_input("PE Objetivo Global", value=25)
    default_quality = st.slider("Quality Score Pordefecto", 0, 100, 85)
    
    st.markdown("---")
    if st.button("📸 Guardar Snapshot Histórico"):
        st.session_state["save_snapshot"] = True

# --- CARGA DE DATOS DESDE BASE DE DATOS ---
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

st.title("🏛️ Terminal Cuantitativo Institucional")
st.markdown("---")

df_pos = load_positions()
df_cash = load_cash_flows()
df_tx = load_transactions()
df_snap = load_snapshots()

# Cálculo de Liquidez
cash_deposits = df_cash['amount'].sum() if not df_cash.empty else 0.0
total_cost_basis = (df_pos['quantity'] * df_pos['average_cost']).sum() if not df_pos.empty else 0.0
total_cash = cash_deposits - total_cost_basis

total_market_value = 0.0
total_unrealized_pl = 0.0
portfolio_net_worth = total_cash

df_enriched = pd.DataFrame()

if not df_pos.empty:
    with st.spinner("Descargando data de mercado y calculando métricas (yfinance)..."):
        tickers = df_pos['ticker'].tolist()
        df_quant = fetch_quant_data(tickers)
        
        if not df_quant.empty:
            # Unir datos
            df_enriched = pd.merge(df_pos, df_quant, on='ticker', how='left')
            
            # Si un ticker no descargó precio, usamos su costo promedio
            df_enriched['current_price'] = df_enriched['current_price'].fillna(df_enriched['average_cost'])
            
            # Cálculos financieros base
            df_enriched['market_value'] = df_enriched['quantity'] * df_enriched['current_price']
            df_enriched['cost_basis'] = df_enriched['quantity'] * df_enriched['average_cost']
            df_enriched['unrealized_pl'] = df_enriched['market_value'] - df_enriched['cost_basis']
            df_enriched['unrealized_pl_pct'] = (df_enriched['unrealized_pl'] / df_enriched['cost_basis']) * 100
            
            # Calcular margin_of_safety heurístico (si tenemos fv graham guardado)
            df_enriched['margin_of_safety'] = 0.0
            for idx, row in df_enriched.iterrows():
                if pd.notna(row['fair_value_graham']) and row['fair_value_graham'] > 0:
                    df_enriched.at[idx, 'margin_of_safety'] = (row['fair_value_graham'] - row['current_price']) / row['current_price']
            
            # Ejecutar motor de scoring por fila
            scores = df_enriched.apply(lambda r: calculate_scores(r, default_quality), axis=1)
            scores_df = pd.DataFrame(list(scores))
            df_enriched = pd.concat([df_enriched, scores_df], axis=1)
            
            total_market_value = df_enriched['market_value'].sum()
            total_unrealized_pl = df_enriched['unrealized_pl'].sum()
            portfolio_net_worth = total_market_value + total_cash
            
            df_enriched['weight'] = df_enriched['market_value'] / portfolio_net_worth if portfolio_net_worth > 0 else 0

# --- LÓGICA DE GUARDADO DE SNAPSHOT ---
if st.session_state.get("save_snapshot"):
    try:
        with Session(engine) as session:
            today = date.today()
            exist = session.query(PortfolioSnapshot).filter_by(date=today).first()
            if not exist:
                snap = PortfolioSnapshot(date=today, total_value=portfolio_net_worth, cash=total_cash, unrealized_pl=total_unrealized_pl)
                session.add(snap)
                session.commit()
                st.sidebar.success("📸 Snapshot de hoy guardado exitosamente.")
            else:
                st.sidebar.warning("⚠️ Ya existe un snapshot para el día de hoy.")
    except Exception as e:
        st.sidebar.error(f"Error guardando snapshot: {e}")
    st.session_state["save_snapshot"] = False

# Tarjetas Métricas
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Valor del Portafolio", f"${portfolio_net_worth:,.2f}")
col2.metric("Efectivo", f"${total_cash:,.2f}")
col3.metric("Inv. Activa", f"${total_cost_basis:,.2f}")
col4.metric("P/L Abierto", f"${total_unrealized_pl:,.2f}", delta=f"{(total_unrealized_pl/total_cost_basis*100):.2f}%" if total_cost_basis > 0 else "0.00%")
col5.metric("Riesgo Beta", f"{(df_enriched['beta'] * df_enriched['weight']).sum():.2f}" if not df_enriched.empty else "0.0")

st.markdown("---")

tab_dash, tab_reb, tab_esc, tab_watch, tab_tx = st.tabs([
    "📊 Holdings", "🎯 Señales & Rebalanceo", "🌪️ Evolución & Riesgo", "🔍 Watchlist", "⚙️ Bitácora"
])

with tab_dash:
    st.subheader("📊 Inventario y Métricas Institucionales")
    if not df_enriched.empty:
        disp_cols = ['ticker', 'current_price', 'quantity', 'cost_basis', 'market_value', 'weight', 'unrealized_pl_pct', 'Signal']
        df_disp = df_enriched[disp_cols].copy()
        
        st.dataframe(
            df_disp, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "ticker": "Símbolo",
                "current_price": st.column_config.NumberColumn("Precio Actual", format="$%.2f"),
                "quantity": st.column_config.NumberColumn("Acciones", format="%.2f"),
                "cost_basis": st.column_config.NumberColumn("Costo Base", format="$%.2f"),
                "market_value": st.column_config.NumberColumn("Valor Mercado", format="$%.2f"),
                "weight": st.column_config.NumberColumn("Peso", format="%.2%"),
                "unrealized_pl_pct": st.column_config.NumberColumn("P/L %", format="%.2f%%"),
                "Signal": "Señal Cuantitativa"
            }
        )
    else:
        st.info("No hay posiciones para mostrar.")

with tab_reb:
    st.subheader("🎯 Buy List & Rebalanceador")
    st.markdown("Basado en los algoritmos de ConvictionScore, ValueScore y RiskScore.")
    
    if not df_enriched.empty:
        df_buy = df_enriched[['ticker', 'ConvictionScore', 'ValueScore', 'TrendScore', 'RiskScore', 'Signal', 'weight']].copy()
        df_buy = df_buy.sort_values(by='ConvictionScore', ascending=False)
        
        # Position Sizing Dinámico
        # Asignamos el peso objetivo basado en la convicción y acotado al max_weight
        df_buy['target_weight'] = (df_buy['ConvictionScore'] / df_buy['ConvictionScore'].sum())
        df_buy['target_weight'] = df_buy['target_weight'].clip(upper=max_weight)
        
        # Re-normalizar después del clipping para que sume 1 - target_cash
        target_invested = 1.0 - target_cash
        current_invested = df_buy['target_weight'].sum()
        if current_invested > 0:
            df_buy['target_weight'] = (df_buy['target_weight'] / current_invested) * target_invested
            
        df_buy['weight_delta'] = df_buy['target_weight'] - df_buy['weight']
        
        # Determinar Acción a tomar
        df_buy['Action'] = df_buy.apply(lambda r: "COMPRAR" if r['weight_delta'] > 0.01 else ("REDUCIR" if r['weight_delta'] < -0.01 else "MANTENER"), axis=1)
        
        st.dataframe(
            df_buy[['ticker', 'ConvictionScore', 'Signal', 'weight', 'target_weight', 'weight_delta', 'Action']],
            use_container_width=True, hide_index=True,
            column_config={
                "weight": st.column_config.NumberColumn("Peso Actual", format="%.2%"),
                "target_weight": st.column_config.NumberColumn("Peso Sugerido", format="%.2%"),
                "weight_delta": st.column_config.NumberColumn("Delta a Ajustar", format="%.2%"),
            }
        )

with tab_esc:
    st.subheader("🌪️ Evolución Histórica y Pruebas de Estrés")
    colA, colB = st.columns([2, 1])
    
    with colA:
        st.markdown("**Evolución del Valor del Portafolio**")
        if not df_snap.empty:
            st.line_chart(df_snap.set_index("date")[["total_value"]])
        else:
            st.info("Guarda snapshots desde la barra lateral para ver tu gráfica de evolución.")
            
    with colB:
        st.markdown("**Test de Escenarios (Impacto en PNL)**")
        if not df_enriched.empty:
            # Calcular Beta ajustado
            port_beta = (df_enriched['beta'] * df_enriched['weight']).sum()
            val = portfolio_net_worth
            
            scenarios = [
                {"Escenario": "Corrección Merc. (-10%)", "Impacto": -0.10 * port_beta * val},
                {"Escenario": "Bear Market (-25%)", "Impacto": -0.25 * port_beta * val},
                {"Escenario": "Crisis Grave (-40%)", "Impacto": -0.40 * port_beta * val},
            ]
            df_esc = pd.DataFrame(scenarios)
            st.dataframe(df_esc, hide_index=True, column_config={"Impacto": st.column_config.NumberColumn(format="$%.2f")})

with tab_watch:
    st.subheader("🔍 Calculadora de Margen de Seguridad")
    with st.form("valuation_form"):
        c1, c2, c3, c4 = st.columns(4)
        eval_ticker = c1.text_input("Ticker").upper()
        growth_est = c2.number_input("Crecimiento % (g)", value=15.0)
        pe_target = c3.number_input("P/E Objetivo", value=25.0)
        bond_y = c4.number_input("Tasa Bonos %", value=4.4)
        submit_val = st.form_submit_button("Calcular")
        
    if submit_val and eval_ticker:
        with st.spinner(f"Consultando fundamentales..."):
            df_eval = fetch_live_data([eval_ticker])
            if not df_eval.empty:
                res = calculate_fair_value(df_eval.iloc[0]['eps'], pe_target, growth_est, df_eval.iloc[0]['current_price'], bond_y)
                st.success(f"Fair Value Ponderado: **${res['fv_final']:,.2f}** | Margen de Seguridad: **{res['margin_of_safety']*100:.2f}%**")

with tab_tx:
    st.subheader("⚙️ Registro y Bitácora de Transacciones")
    st.markdown("Gestiona tu inventario, compra/venta de acciones y flujo de efectivo.")

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
                op_reason = st.text_input("Nota (Ej: 'Dividendo AVGO' o 'Aporte mensual')")
            
            op_ticker = "Efectivo"
            op_qty = 1.0

        else: # Acción
            col1, col2, col3 = st.columns(3)
            with col1:
                op_date = st.date_input("Fecha")
                op_action = st.selectbox("Operación", ["BUY", "SELL"])
            with col2:
                op_ticker = st.text_input("Ticker", placeholder="Ej: META").upper()
                op_qty = st.number_input("Cantidad", min_value=0.01, step=0.01, format="%.2f")
            with col3:
                op_price = st.number_input("Precio por Acción (USD)", min_value=0.01, step=0.01, format="%.2f")
                op_reason = st.text_input("Motivo")

        submit_op = st.form_submit_button("Registrar Transacción")

    if submit_op:
        try:
            with Session(engine) as session:
                if instrumento != "Efectivo" and not op_ticker:
                    st.session_state["op_err"] = "⚠️ Debes ingresar un Ticker válido."
                    st.rerun()
                
                # A. Registro en Bitácora (Transactions)
                nueva_tx = Transaction(
                    date=op_date, ticker=op_ticker, action=op_action, 
                    quantity=op_qty, price=op_price, reason=op_reason
                )
                session.add(nueva_tx)

                # B. Lógica de Inventario (Solo aplica para Acciones)
                if instrumento == "Acción":
                    pos = session.query(Position).filter_by(ticker=op_ticker).first()
                    if op_action == "BUY":
                        if pos:
                            total_cost_prev = pos.quantity * pos.average_cost
                            new_total_cost = total_cost_prev + (op_qty * op_price)
                            pos.quantity += op_qty
                            pos.average_cost = new_total_cost / pos.quantity
                        else:
                            nueva_pos = Position(ticker=op_ticker, quantity=op_qty, average_cost=op_price)
                            session.add(nueva_pos)
                    
                    elif op_action == "SELL":
                        if pos:
                            pos.quantity -= op_qty
                            if pos.quantity <= 0:
                                session.delete(pos)
                        else:
                            st.session_state["op_err"] = "⚠️ Intento de venta de un activo que no está en el inventario."
                            st.rerun()

                # C. Lógica de Flujo de Efectivo (Para el Dashboard de Liquidez)
                elif instrumento == "Efectivo":
                    multiplier = -1 if op_action == "WITHDRAW" else 1
                    nuevo_cf = CashFlow(date=op_date, amount=op_price * multiplier, type=op_action)
                    session.add(nuevo_cf)

                session.commit()
                st.session_state["op_msg"] = f"✅ Operación de {instrumento} registrada correctamente."
            st.rerun()
        except Exception as e:
            st.error(f"Error crítico en base de datos: {e}")

    # Panel de Eliminación y Visualización de la Bitácora
    st.divider()
    st.subheader("📜 Historial de Transacciones")
    
    if not df_tx.empty:
        with st.expander("🛠️ Modo Edición: Eliminar Registro"):
            st.warning("Al eliminar una transacción de la bitácora, el inventario **no** se recalcula automáticamente.")
            col_id, col_btn = st.columns([3, 1])
            with col_id:
                del_id = st.number_input("Ingresa el ID de la transacción a eliminar:", min_value=int(df_tx['id'].min()), max_value=int(df_tx['id'].max()), step=1)
            with col_btn:
                st.write("") 
                if st.button("Eliminar", type="primary"):
                    with Session(engine) as session:
                        tx_to_del = session.query(Transaction).filter_by(id=del_id).first()
                        if tx_to_del:
                            session.delete(tx_to_del)
                            session.commit()
                            st.session_state["op_msg"] = f"🗑️ Transacción ID {del_id} eliminada."
                            st.rerun()
                        else:
                            st.error("ID no encontrado.")

        df_tx_display = df_tx.sort_values(by='date', ascending=False)
        st.dataframe(df_tx_display[['id', 'date', 'ticker', 'action', 'quantity', 'price', 'reason']], use_container_width=True, hide_index=True)
    else:
        st.info("No hay transacciones registradas en la bitácora.")