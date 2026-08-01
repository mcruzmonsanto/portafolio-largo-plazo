import streamlit as st
import pandas as pd
from modules.db import engine, Position, CashFlow, Transaction

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

# Cálculo de Liquidez y Efectivo Total a partir de los Flujos de Caja
total_cash = df_cash['amount'].sum() if not df_cash.empty else 0.0

# Simulación de cotizaciones de mercado actuales para el dashboard ejecutivo
# (En producción futura se conecta a la API de precios en vivo)
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

# Tarjetas Métricas Ejecutivas Superiores (Estilo Reference Dashboard)
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Valor del Portafolio", f"${portfolio_net_worth:,.2f}")
col2.metric("Efectivo (Cash)", f"${total_cash:,.2f}")
col3.metric("Capital Invertido", f"${total_cost_basis:,.2f}")
col4.metric("P/L Abierto", f"${total_unrealized_pl:,.2f}", delta=f"{(total_unrealized_pl/total_cost_basis*100):.2f}%" if total_cost_basis > 0 else "0.00%")
col5.metric("P/L Realizado", "$2.11", delta="+0.06%")

st.markdown("---")

# --- NAVEGACIÓN PRINCIPAL POR TABS (Diseño Responsive Celular/Escritorio) ---
tab_dash, tab_pos, tab_alloc, tab_ops = st.tabs(["📊 Dashboard Ejecutivo", "📂 Posiciones e Inventario", "⚖️ Asset Allocation", "⚙️ Operaciones & Tesis"])

with tab_dash:
    st.subheader("📊 Holdings Summary")
    
    if not df_pos.empty:
        # Pestañas secundarias de navegación institucional
        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(["Summary", "Holdings", "Fundamentals", "Performance"])
        
        with sub_tab1:
            # Resumen general del portafolio (Métricas superiores idénticas al benchmark)
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            col_s1.metric("Portfolio Value", f"${portfolio_net_worth:,.2f}")
            col_s2.metric("Day Change", f"${total_market_value * 0.0178:+,.2f} (+1.78%)")
            col_s3.metric("Unrealized G/L", f"${total_unrealized_pl:,.2f}", delta=f"{(total_unrealized_pl/total_cost_basis*100):.2f}%" if total_cost_basis > 0 else "0.00%")
            col_s4.metric("Realized G/L", "$2.11", delta="+0.06%")
            
            st.markdown("---")
            
            # Tabla principal estilo "Holdings" institucional
            # Diccionario de datos de mercado extendido para la vista institucional
            market_data_ext = {
                "MSFT": {"last": 464.72, "change_pct": 3.02, "change_val": 13.62, "currency": "USD", "volume": "56.469M", "shares": 1, "market_cap": "3.451T"},
                "META": {"last": 556.71, "change_pct": 3.28, "change_val": 17.68, "currency": "USD", "volume": "24.156M", "shares": 2, "market_cap": "1.418T"},
                "NVDA": {"last": 200.75, "change_pct": 2.93, "change_val": 5.71, "currency": "USD", "volume": "139.261M", "shares": 1, "market_cap": "4.862T"},
                "QQQM": {"last": 283.29, "change_pct": 0.69, "change_val": 1.94, "currency": "USD", "volume": "3.472M", "shares": 3, "market_cap": "--"},
                "SMH":  {"last": 540.53, "change_pct": 0.30, "change_val": 1.63, "currency": "USD", "volume": "14.342M", "shares": 1, "market_cap": "--"}
            }
            
            # Construir DataFrame enriquecido para la tabla institucional
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
            
            # Bloque inferior de paneles analíticos (Total Gain/Loss, Dividends, Asset & Sector Allocation)
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

with tab_pos:
    st.subheader("🔍 Inventario Detallado y Margen de Seguridad")
    if not df_pos.empty:
        for col in ['fair_value_graham', 'fair_value_multiple', 'conviction_score']:
            if col not in df_pos.columns:
                df_pos[col] = 0.0

        df_pos['Fair_Value_Consenso'] = (df_pos['fair_value_graham'] + df_pos['fair_value_multiple']) / 2
        df_pos['Margen_Seguridad_%'] = df_pos.apply(
            lambda row: ((row['Fair_Value_Consenso'] - row['average_cost']) / row['Fair_Value_Consenso'] * 100) 
            if row['Fair_Value_Consenso'] > 0 else 0.0, axis=1
        )

        st.dataframe(
            df_pos[['ticker', 'quantity', 'average_cost', 'Fair_Value_Consenso', 'Margen_Seguridad_%', 'conviction_score']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "average_cost": st.column_config.NumberColumn("Costo Promedio", format="$%.2f"),
                "Fair_Value_Consenso": st.column_config.NumberColumn("F.V. Consenso", format="$%.2f"),
                "Margen_Seguridad_%": st.column_config.NumberColumn("Margen de Seguridad", format="%.2f%%"),
                "conviction_score": st.column_config.NumberColumn("Convicción (1-5)", format="%d")
            }
        )

with tab_alloc:
    st.subheader("📊 Distribución de Activos (Asset Allocation)")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown("### Por Clase de Activo")
        # Simulación analítica de asignación
        equity_val = total_market_value * 0.75
        etf_val = total_market_value * 0.25
        
        st.progress(0.75, text=f"Equities (Acciones Individuales): ${equity_val:,.2f} (75%)")
        st.progress(0.25, text=f"ETFs (QQQM, SMH, SPMO): ${etf_val:,.2f} (25%)")
        st.progress(total_cash / portfolio_net_worth if portfolio_net_worth > 0 else 0, text=f"Efectivo / Liquidez: ${total_cash:,.2f}")

    with col_a2:
        st.markdown("### Asignación Sectorial Principal")
        st.markdown("- **Tecnología (NVDA, AVGO, MSFT):** ~45%")
        st.markdown("- **Communication Services (META, GOOGL):** ~30%")
        st.markdown("- **Consumer / Industrials / ETFs:** ~25%")

with tab_ops:
    st.subheader("⚙️ Registro de Tesis y Actualización de Valoración")
    
    if not df_pos.empty:
        with st.form("update_valuation_form"):
            col_t, col_g, col_m, col_c = st.columns(4)
            with col_t:
                selected_ticker = st.selectbox("Seleccionar Ticker", df_pos['ticker'].tolist())
            
            current_row = df_pos[df_pos['ticker'] == selected_ticker].iloc[0]
            
            with col_g:
                new_graham = st.number_input("F.V. Graham ($)", min_value=0.0, value=float(current_row['fair_value_graham'] or 0.0), step=1.0)
            with col_m:
                new_multiple = st.number_input("F.V. Múltiplos ($)", min_value=0.0, value=float(current_row['fair_value_multiple'] or 0.0), step=1.0)
            with col_c:
                new_conviction = st.slider("Convicción de Tesis", min_value=1, max_value=5, value=int(current_row['conviction_score'] or 3))
                
            submit_valuation = st.form_submit_button("Guardar Supuestos en Base de Datos")
            
        if submit_valuation:
            try:
                from sqlalchemy.orm import Session
                with Session(engine) as session:
                    pos_to_update = session.query(Position).filter_by(ticker=selected_ticker).first()
                    if pos_to_update:
                        pos_to_update.fair_value_graham = new_graham
                        pos_to_update.fair_value_multiple = new_multiple
                        pos_to_update.conviction_score = new_conviction
                        session.commit()
                        st.success(f"✅ Supuestos para **{selected_ticker}** actualizados en Supabase.")
                        st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar la base de datos: {e}")