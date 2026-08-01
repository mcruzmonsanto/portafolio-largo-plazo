import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from modules.db import engine, Position, Transaction, CashFlow
from modules.market_data import fetch_live_data
from modules.valuation import calculate_fair_value

st.set_page_config(page_title="Portafolio Value", page_icon="🏛️", layout="wide")

# --- FUNCIONES DE ACCESO A DATOS ---
def load_positions():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM positions", conn)
    return df

def load_cash_flows():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM cash_flows", conn)
    return df

def load_transactions():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM transactions", conn)
    return df

# --- UI PRINCIPAL ---
st.title("🏛️ Sistema de Portafolio Largo Plazo")

tab_dash, tab_pos, tab_watch, tab_ops = st.tabs([
    "📊 Dashboard", 
    "💼 Posiciones", 
    "🔍 Watchlist", 
    "⚙️ Operaciones"
])

# Carga base de datos
df_pos = load_positions()
df_cf = load_cash_flows()

# Integración de API (Ejecución cacheada)
df_live = pd.DataFrame()
if not df_pos.empty:
    tickers = df_pos['ticker'].tolist()
    with st.spinner("Actualizando datos de mercado..."):
        df_live = fetch_live_data(tickers)
    
    # Cruzamos el inventario (SQLite) con los precios en vivo (yfinance)
    df_merged = pd.merge(df_pos, df_live, on='ticker', how='left')
    
    # Cálculos financieros
    df_merged['Costo_Total'] = df_merged['quantity'] * df_merged['average_cost']
    df_merged['Valor_Mercado'] = df_merged['quantity'] * df_merged['current_price']
    df_merged['PL_Abierto'] = df_merged['Valor_Mercado'] - df_merged['Costo_Total']
    df_merged['PL_Pct'] = (df_merged['PL_Abierto'] / df_merged['Costo_Total']) * 100

# --- PESTAÑA 1: DASHBOARD EJECUTIVO ---
with tab_dash:
    st.subheader("Resumen Ejecutivo")
    
    if not df_pos.empty and not df_live.empty:
        total_invested = df_merged['Costo_Total'].sum()
        market_value = df_merged['Valor_Mercado'].sum()
        open_pl = df_merged['PL_Abierto'].sum()
        open_pl_pct = (open_pl / total_invested) * 100 if total_invested > 0 else 0
        
        aportes_netos = df_cf['amount'].sum() if not df_cf.empty else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Capital Invertido", f"${total_invested:,.2f}")
        col2.metric("Valor de Mercado", f"${market_value:,.2f}", f"{open_pl_pct:,.2f}%", delta_color="normal")
        col3.metric("P/L Abierto", f"${open_pl:,.2f}")
        col4.metric("Aportes Netos", f"${aportes_netos:,.2f}")
        
    else:
        st.warning("No hay datos suficientes para mostrar el dashboard.")

# --- PESTAÑA 2: POSICIONES E INVENTARIO ---
with tab_pos:
    st.subheader("📊 Inventario y Margen de Seguridad")
    st.markdown("Auditoría de posiciones bajo los criterios de Benjamin Graham y Múltiplos Históricos.")

    df_pos = load_positions()
    
    if not df_pos.empty:
        # Asegurar columnas analíticas si vienen vacías de la BD
        for col in ['fair_value_graham', 'fair_value_multiple', 'conviction_score']:
            if col not in df_pos.columns:
                df_pos[col] = 0.0

        # Cálculos analíticos de valor razonable y margen de seguridad
        # F.V. Consenso = Promedio entre Graham y Múltiplos
        df_pos['Fair_Value_Consenso'] = (df_pos['fair_value_graham'] + df_pos['fair_value_multiple']) / 2
        
        # Margen de Seguridad % = (Fair Value Consenso - Costo Promedio) / Fair Value Consenso * 100
        # (Si Fair Value es 0 o nulo, evitamos división por cero)
        df_pos['Margen_Seguridad_%'] = df_pos.apply(
            lambda row: ((row['Fair_Value_Consenso'] - row['average_cost']) / row['Fair_Value_Consenso'] * 100) 
            if row['Fair_Value_Consenso'] > 0 else 0.0, axis=1
        )

        # Visualización en tabla estructurada
        st.markdown("### 📋 Resumen de Cartera y Descuento Teórico")
        st.dataframe(
            df_pos[['ticker', 'quantity', 'average_cost', 'fair_value_graham', 'fair_value_multiple', 'Fair_Value_Consenso', 'Margen_Seguridad_%', 'conviction_score']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "average_cost": st.column_config.NumberColumn("Costo Promedio", format="$%.2f"),
                "fair_value_graham": st.column_config.NumberColumn("F.V. Graham", format="$%.2f"),
                "fair_value_multiple": st.column_config.NumberColumn("F.V. Múltiplos", format="$%.2f"),
                "Fair_Value_Consenso": st.column_config.NumberColumn("F.V. Consenso", format="$%.2f"),
                "Margen_Seguridad_%": st.column_config.NumberColumn("Margen de Seguridad", format="%.2f%%"),
                "conviction_score": st.column_config.NumberColumn("Convicción (1-5)", format="%d")
            }
        )

        # Panel de Edición de Tesis y Valoración por Ticker
        st.divider()
        st.subheader("🛠️ Actualizar Supuestos de Valoración (Tesis)")
        
        with st.form("update_valuation_form"):
            col_t, col_g, col_m, col_c = st.columns(4)
            with col_t:
                selected_ticker = st.selectbox("Seleccionar Ticker", df_pos['ticker'].tolist())
            
            # Obtener valores actuales de la fila seleccionada
            current_row = df_pos[df_pos['ticker'] == selected_ticker].iloc[0]
            
            with col_g:
                new_graham = st.number_input("F.V. Graham (USD)", min_value=0.0, value=float(current_row['fair_value_graham'] or 0.0), step=1.0, format="%.2f")
            with col_m:
                new_multiple = st.number_input("F.V. Múltiplos (USD)", min_value=0.0, value=float(current_row['fair_value_multiple'] or 0.0), step=1.0, format="%.2f")
            with col_c:
                new_conviction = st.slider("Convicción de Tesis", min_value=1, max_value=5, value=int(current_row['conviction_score'] or 3))
                
            submit_valuation = st.form_submit_button("Actualizar Supuestos en Base de Datos")
            
        if submit_valuation:
            try:
                from sqlalchemy.orm import Session
                from modules.db import engine, Position
                
                with Session(engine) as session:
                    pos_to_update = session.query(Position).filter_by(ticker=selected_ticker).first()
                    if pos_to_update:
                        pos_to_update.fair_value_graham = new_graham
                        pos_to_update.fair_value_multiple = new_multiple
                        pos_to_update.conviction_score = new_conviction
                        session.commit()
                        st.success(f"[OK] Supuestos para **{selected_ticker}** actualizados correctamente.")
                        st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar la base de datos: {e}")

        st.info("💡 **Marco Munger/Graham:** Recuerda que la única justificación para deshacerse de una posición de alta convicción es el deterioro estructural de la tesis de negocio, nunca la volatilidad de precios del mercado.")
    else:
        st.warning("No hay posiciones registradas en el inventario.")

# --- PESTAÑA 3: WATCHLIST Y VALORACIÓN ---
with tab_watch:
    st.subheader("🔍 Calculadora de Margen de Seguridad")
    
    st.markdown("Calcula el Valor Intrínseco ponderado (**40% Graham / 60% Múltiplos**).")
    
    # Usamos un form para que la API no se llame con cada tecla que presionas
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
            # Reutilizamos nuestra función cacheada
            df_eval = fetch_live_data([eval_ticker])
            
            if not df_eval.empty and df_eval.iloc[0]['current_price'] > 0:
                data = df_eval.iloc[0]
                eps_actual = data['eps']
                precio_actual = data['current_price']
                
                # Ejecutamos el motor de cálculo
                resultado = calculate_fair_value(
                    eps=eps_actual, 
                    target_pe=pe_target, 
                    growth_rate=growth_est, 
                    current_price=precio_actual, 
                    bond_yield=bond_y
                )
                
                # Renderizado de resultados
                st.divider()
                st.markdown(f"### Resultados para **{eval_ticker}**")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Precio Actual", f"${precio_actual:,.2f}")
                c2.metric("EPS (TTM)", f"${eps_actual:,.2f}")
                c3.metric("Fair Value Graham", f"${resultado['fv_graham']:,.2f}")
                c4.metric("Fair Value Múltiplos", f"${resultado['fv_multiple']:,.2f}")
                
                st.markdown("---")
                rc1, rc2 = st.columns(2)
                
                # Formateo visual del Fair Value Final
                rc1.metric(
                    "Fair Value Final (Ponderado)", 
                    f"${resultado['fv_final']:,.2f}",
                    f"{(resultado['fv_final'] - precio_actual) / precio_actual * 100:,.2f}% vs Precio Actual"
                )
                
                # Formateo visual del Margen de Seguridad
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

# --- PESTAÑA 4: OPERACIONES ---
with tab_ops:
    st.subheader("⚙️ Registro y Bitácora Avanzada")
    st.markdown("Gestiona inventario, estrategias de opciones y flujo de efectivo.")

    # 1. Sistema de Notificaciones (Sobrevive al rerun)
    if "op_msg" in st.session_state:
        st.success(st.session_state["op_msg"])
        del st.session_state["op_msg"]
    if "op_err" in st.session_state:
        st.error(st.session_state["op_err"])
        del st.session_state["op_err"]

    # 2. Selector Dinámico (Fuera del form para permitir redibujado de la UI)
    instrumento = st.radio("Tipo de Instrumento", ["Acción", "Opción", "Efectivo"], horizontal=True)

    # 3. Formulario Adaptativo
    with st.form("ops_form"):
        if instrumento == "Efectivo":
            col1, col2 = st.columns(2)
            with col1:
                op_date = st.date_input("Fecha de Ejecución")
                op_action = st.selectbox("Movimiento", ["DEPOSIT", "WITHDRAW", "DIVIDEND"])
            with col2:
                op_price = st.number_input("Monto (USD)", min_value=0.01, step=1.0, format="%.2f")
                op_reason = st.text_input("Nota (Ej: 'Dividendo AVGO' o 'Aporte mensual')")
            
            # Variables nulas para mantener consistencia en base de datos
            op_ticker, op_qty, op_strategy, op_strike, op_expiration = None, None, None, None, None

        elif instrumento == "Opción":
            col1, col2, col3 = st.columns(3)
            with col1:
                op_date = st.date_input("Fecha de Ejecución")
                op_action = st.selectbox("Tipo de Orden", ["BUY (BTO/BTC)", "SELL (STO/STC)"])
                op_strategy = st.selectbox("Estrategia", ["Cash-Secured Put", "Covered Call", "LEAPS", "Long Call/Put"])
            with col2:
                op_ticker = st.text_input("Ticker Subyacente", placeholder="Ej: PLTR").upper()
                op_qty = st.number_input("Cantidad (Contratos)", min_value=1, step=1)
                op_price = st.number_input("Prima total pagada/cobrada (USD)", min_value=0.01, step=1.0, format="%.2f")
            with col3:
                op_strike = st.number_input("Strike Price", min_value=0.01, step=0.5, format="%.2f")
                op_expiration = st.date_input("Fecha de Expiración")
                op_reason = st.text_input("Motivo / Tesis")

        else: # Acción
            col1, col2, col3 = st.columns(3)
            with col1:
                op_date = st.date_input("Fecha de Ejecución")
                op_action = st.selectbox("Tipo de Orden", ["BUY", "SELL"])
            with col2:
                op_ticker = st.text_input("Ticker", placeholder="Ej: META").upper()
                op_qty = st.number_input("Cantidad de Acciones", min_value=0.01, step=0.01, format="%.2f")
            with col3:
                op_price = st.number_input("Precio de Ejecución (USD)", min_value=0.01, step=0.01, format="%.2f")
                op_reason = st.text_input("Motivo (Ej: Deterioro de tesis)")
                
            op_strategy, op_strike, op_expiration = None, None, None

        submit_op = st.form_submit_button("Registrar Operación")

    # 4. Lógica de Procesamiento
    if submit_op:
        try:
            with Session(engine) as session:
                # Validar ticker si no es efectivo
                if instrumento != "Efectivo" and not op_ticker:
                    st.session_state["op_err"] = "⚠️ Debes ingresar un Ticker válido."
                    st.rerun()
                
                # A. Registro en Bitácora Maestra
                nueva_tx = Transaction(
                    date=op_date, instrument=instrumento, action=op_action, 
                    strategy=op_strategy, ticker=op_ticker, quantity=op_qty, 
                    price=op_price, strike=op_strike, expiration=op_expiration, 
                    reason=op_reason
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

                # C. Lógica de Flujo de Efectivo (Para el Dashboard)
                elif instrumento == "Efectivo":
                    multiplier = -1 if op_action == "WITHDRAW" else 1
                    nuevo_cf = CashFlow(date=op_date, amount=op_price * multiplier, type=op_action)
                    session.add(nuevo_cf)

                session.commit()
                st.session_state["op_msg"] = f"✅ Operación de {instrumento} registrada correctamente."
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Error crítico en base de datos: {e}")

    # 5. Visualización y Panel de Control de Eliminación
    st.divider()
    st.subheader("📜 Historial de Transacciones")
    
    # Función para cargar transacciones (definida previamente arriba)
    df_tx = load_transactions()
    
    if not df_tx.empty:
        # Panel para eliminar registros erróneos
        with st.expander("🛠️ Modo Edición: Eliminar Registro"):
            st.warning("Al eliminar una transacción de la bitácora, **no** se recalcula automáticamente el inventario. Ajusta la posición manualmente si es necesario mediante una operación compensatoria.")
            col_id, col_btn = st.columns([3, 1])
            with col_id:
                del_id = st.number_input("Ingresa el ID de la transacción a eliminar:", min_value=int(df_tx['id'].min()), max_value=int(df_tx['id'].max()), step=1)
            with col_btn:
                st.write("") # Espaciador
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

        df_tx = df_tx.sort_values(by='date', ascending=False)
        
        # Formateo dinámico para manejar nulos en las columnas de opciones
        df_tx_display = df_tx[['id', 'date', 'ticker', 'action', 'quantity', 'price', 'reason']].copy()
        
        st.dataframe(
            df_tx_display,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay transacciones registradas en la bitácora.")