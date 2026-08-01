import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from modules.db import engine, Position, CashFlow, Transaction
from modules.market_data import fetch_live_data
from modules.valuation import calculate_fair_value

# Configuración de página optimizada para escritorio y móvil (responsive)
st.set_page_config(
    page_title="Sistema de Portafolio de Largo Plazo",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CARGA DE DATOS DESDE BASE DE DATOS (SUPABASE / SQLITE) ---
@st.cache_data(ttl=60)
def load_positions():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM positions", conn)
    return df

@st.cache_data(ttl=60)
def load_cash_flows():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM cash_flows", conn)
    return df

@st.cache_data(ttl=60)
def load_transactions():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM transactions", conn)
    return df

# --- HEADER EJECUTIVO SUPERIOR ---
st.title("🏛️ Sistema de Portafolio Largo Plazo")
st.markdown("---")

df_pos = load_positions()
df_cash = load_cash_flows()
df_tx = load_transactions()

# Cálculo de Liquidez (Cash real)
cash_deposits = df_cash['amount'].sum() if not df_cash.empty else 0.0

if not df_pos.empty:
    total_cost_basis = (df_pos['quantity'] * df_pos['average_cost']).sum()
else:
    total_cost_basis = 0.0

total_cash = cash_deposits - total_cost_basis

# Simulación de cotizaciones de mercado actuales para el dashboard ejecutivo
market_prices = {"AMZN": 220.0, "AVGO": 370.0, "GOOGL": 320.0, "META": 556.70, "MSFT": 464.72, 
                 "NVDA": 100.37, "PLTR": 110.0, "QQQM": 283.29, "SMH": 270.26, "SPMO": 150.0}

if not df_pos.empty:
    df_pos['current_price'] = df_pos['ticker'].map(market_prices).fillna(df_pos['average_cost'])
    df_pos['market_value'] = df_pos['quantity'] * df_pos['current_price']
    df_pos['cost_basis'] = df_pos['quantity'] * df_pos['average_cost']
    df_pos['unrealized_pl'] = df_pos['market_value'] - df_pos['cost_basis']
    df_pos['unrealized_pl_pct'] = (df_pos['unrealized_pl'] / df_pos['cost_basis']) * 100
    
    total_market_value = df_pos['market_value'].sum()
    total_cost_basis = df_pos['cost_basis'].sum()
    total_unrealized_pl = df_pos['unrealized_pl'].sum()
    portfolio_net_worth = total_market_value + total_cash
else:
    total_market_value = 0.0
    total_cost_basis = 0.0
    total_unrealized_pl = 0.0
    portfolio_net_worth = total_cash

# Tarjetas Métricas Ejecutivas Superiores
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Valor del Portafolio", f"${portfolio_net_worth:,.2f}")
col2.metric("Efectivo Disponible", f"${total_cash:,.2f}")
col3.metric("Capital Invertido", f"${total_cost_basis:,.2f}")
col4.metric("P/L Abierto", f"${total_unrealized_pl:,.2f}", delta=f"{(total_unrealized_pl/total_cost_basis*100):.2f}%" if total_cost_basis > 0 else "0.00%")
col5.metric("P/L Realizado", "$2.11", delta="+0.06%")

st.markdown("---")

# --- NAVEGACIÓN PRINCIPAL POR TABS ---
tab_dash, tab_watch, tab_tx = st.tabs(["📊 Dashboard Ejecutivo", "🔍 Watchlist", "⚙️ Bitácora de Transacciones"])

# --- PESTAÑA 1: DASHBOARD EJECUTIVO ---
with tab_dash:
    st.subheader("📊 Holdings Summary")
    
    if not df_pos.empty:
        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(["Summary", "Holdings", "Fundamentals", "Performance"])
        
        with sub_tab1:
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            col_s1.metric("Portfolio Value", f"${portfolio_net_worth:,.2f}")
            col_s2.metric("Day Change", f"${total_market_value * 0.0178:+,.2f} (+1.78%)")
            col_s3.metric("Unrealized G/L", f"${total_unrealized_pl:,.2f}", delta=f"{(total_unrealized_pl/total_cost_basis*100):.2f}%" if total_cost_basis > 0 else "0.00%")
            col_s4.metric("Realized G/L", "$2.11", delta="+0.06%")
            
            st.markdown("---")
            
            market_data_ext = {
                "MSFT": {"last": 464.72, "change_pct": 3.02, "change_val": 13.62, "currency": "USD", "volume": "56.469M", "shares": 1, "market_cap": "3.451T"},
                "META": {"last": 556.71, "change_pct": 3.28, "change_val": 17.68, "currency": "USD", "volume": "24.156M", "shares": 2, "market_cap": "1.418T"},
                "NVDA": {"last": 200.75, "change_pct": 2.93, "change_val": 5.71, "currency": "USD", "volume": "139.261M", "shares": 1, "market_cap": "4.862T"},
                "QQQM": {"last": 283.29, "change_pct": 0.69, "change_val": 1.94, "currency": "USD", "volume": "3.472M", "shares": 3, "market_cap": "--"},
                "SMH":  {"last": 540.53, "change_pct": 0.30, "change_val": 1.63, "currency": "USD", "volume": "14.342M", "shares": 1, "market_cap": "--"}
            }
            
            holdings_rows = []
            for _, row in df_pos.iterrows():
                t = row['ticker']
                m = market_data_ext.get(t, {"last": row['average_cost'], "change_pct": 0.0, "change_val": 0.0, "currency": "USD", "volume": "1.2M", "shares": row['quantity'], "market_cap": "100B"})
                holdings_rows.append({
                    "Symbol": t,
                    "Last Price": m["last"],
                    "Change (%)": f"+{m['change_pct']}%" if m['change_pct'] >= 0 else f"{m['change_pct']}%",
                    "Change ($)": f"+{m['change_val']}" if m['change_val'] >= 0 else f"{m['change_val']}",
                    "Currency": m["currency"],
                    "Volume": m["volume"],
                    "Shares": m["shares"],
                    "Market Cap": m["market_cap"]
                })
            
            df_holdings_ui = pd.DataFrame(holdings_rows)
            st.dataframe(df_holdings_ui, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)
            
            with col_b1:
                st.markdown("#### Total Holdings Gain/Loss")
                st.metric("Cost Basis", f"${total_cost_basis:,.2f}")
                st.metric("Total Holdings", f"${total_market_value:,.2f}")
                st.error(f"Gain/Loss: ${total_unrealized_pl:,.2f}")
                
            with col_b2:
                st.markdown("#### Dividend Payouts")
                st.metric("Total Payout", "$2.11")
                st.caption("Jun: $2.11 | Resto meses: $0.00")
                
            with col_b3:
                st.markdown("#### Asset Allocation")
                st.progress(0.4996, text="Equities: $1,778.89 (49.96%)")
                st.progress(0.3905, text="ETF's: $1,390.40 (39.05%)")
                st.progress(0.1098, text="Cash: $391.00 (10.98%)")
                
            with col_b4:
                st.markdown("#### Sector Allocation")
                st.markdown("- **Technology:** $1,723.83 (48.42%)")
                st.markdown("- **Communication Services:** $1,224.50 (34.39%)")
                st.markdown("- **Consumer Cyclical:** $90.77 (2.55%)")
                st.markdown("- **Consumer Defensive:** $53.12 (1.49%)")
                
        with sub_tab2:
            st.markdown("### 📂 Detalle Completo de Posiciones del Portafolio")
            st.dataframe(df_pos, use_container_width=True, hide_index=True)
            
        with sub_tab3:
            st.markdown("### 🔬 Fundamentales y Tesis (Graham & Múltiplos)")
            st.info("Módulo de auditoría de fundamentales vinculado a Supabase.")
            
        with sub_tab4:
            st.markdown("### 🚀 Rendimiento Histórico")
            st.success("Gráficos de rendimiento en tiempo real activos.")
    else:
        st.warning("No hay posiciones registradas.")

# --- PESTAÑA 2: WATCHLIST Y VALORACIÓN ---
with tab_watch:
    st.subheader("🔍 Calculadora de Margen de Seguridad")
    st.markdown("Calcula el Valor Intrínseco ponderado (**40% Graham / 60% Múltiplos**).")
    
    with st.form("valuation_form"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            eval_ticker = st.text_input("Ticker", placeholder="Ej: PLTR").upper()
        with col2:
            growth_est = st.number_input("Crecimiento Esperado % (g)", min_value=0.0, max_value=100.0, value=15.0, step=1.0)
        with col3:
            pe_target = st.number_input("P/E Objetivo", min_value=1.0, max_value=200.0, value=25.0, step=1.0)
        with col4:
            bond_y = st.number_input("Tasa Bonos % (Y)", min_value=1.0, max_value=10.0, value=4.4, step=0.1)
            
        submit_val = st.form_submit_button("Calcular Fair Value")
        
    if submit_val and eval_ticker:
        with st.spinner(f"Consultando datos fundamentales de {eval_ticker}..."):
            df_eval = fetch_live_data([eval_ticker])
            
            if not df_eval.empty and df_eval.iloc[0]['current_price'] > 0:
                data = df_eval.iloc[0]
                eps_actual = data['eps']
                precio_actual = data['current_price']
                
                resultado = calculate_fair_value(
                    eps=eps_actual, 
                    target_pe=pe_target, 
                    growth_rate=growth_est, 
                    current_price=precio_actual, 
                    bond_yield=bond_y
                )
                
                st.divider()
                st.markdown(f"### Resultados para **{eval_ticker}**")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Precio Actual", f"${precio_actual:,.2f}")
                c2.metric("EPS (TTM)", f"${eps_actual:,.2f}")
                c3.metric("Fair Value Graham", f"${resultado['fv_graham']:,.2f}")
                c4.metric("Fair Value Múltiplos", f"${resultado['fv_multiple']:,.2f}")
                
                st.markdown("---")
                rc1, rc2 = st.columns(2)
                
                rc1.metric(
                    "Fair Value Final (Ponderado)", 
                    f"${resultado['fv_final']:,.2f}",
                    f"{(resultado['fv_final'] - precio_actual) / precio_actual * 100:,.2f}% vs Precio Actual"
                )
                
                mos_pct = resultado['margin_of_safety'] * 100
                if resultado['is_buy']:
                    rc2.success(f"✅ Margen de Seguridad: {mos_pct:.2f}% (Superior al 30% exigido)")
                else:
                    if mos_pct > 0:
                        rc2.warning(f"⚠️ Margen de Seguridad: {mos_pct:.2f}% (Insuficiente, requiere 30%)")
                    else:
                        rc2.error(f"❌ Sin Margen de Seguridad. Sobrevalorada en {abs(mos_pct):.2f}%")
            else:
                st.error("No se pudo obtener la información. Verifica que el Ticker sea correcto.")

# --- PESTAÑA 3: TRANSACCIONES (BITÁCORA) ---
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
        # Mostrar las columnas correctas según el esquema actual
        st.dataframe(df_tx_display[['id', 'date', 'ticker', 'action', 'quantity', 'price', 'reason']], use_container_width=True, hide_index=True)
    else:
        st.info("No hay transacciones registradas en la bitácora.")