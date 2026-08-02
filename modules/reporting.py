import io
from datetime import datetime
from fpdf import FPDF
import pandas as pd
from portfolio_config import MAX_STOCK_WEIGHT, MAX_ETF_WEIGHT, KNOWN_ETFS

def format_currency(value):
    if pd.isna(value): return "-"
    if abs(value) >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"

def format_percentage(value, decimals=1):
    if pd.isna(value): return "-"
    return f"{value*100:.{decimals}f}%"

class PDFTearSheet(FPDF):
    def header(self):
        # Logo / Título
        self.set_font('helvetica', 'B', 16)
        self.set_text_color(41, 128, 185)  # Azul
        self.cell(0, 10, 'PORTFOLIO TEAR SHEET', ln=True, align='C')
        
        # Subtítulo y fecha
        self.set_font('helvetica', 'I', 10)
        self.set_text_color(100, 100, 100)
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        self.cell(0, 6, f'Generado el: {date_str}', ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def generate_tear_sheet(df_enriched: pd.DataFrame, portfolio_net_worth: float, total_cash: float, beta_val: float, regime: str, dynamic_min_cash: float):
    pdf = PDFTearSheet()
    pdf.add_page()
    
    # 1. Resumen Ejecutivo
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, 'Resumen Ejecutivo', ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font('helvetica', '', 11)
    pdf.set_text_color(0, 0, 0)
    
    cash_pct = (total_cash / portfolio_net_worth * 100) if portfolio_net_worth > 0 else 0
    
    # Datos en 2 columnas con posiciones absolutas
    y_start = pdf.get_y()
    
    # Columna 1
    pdf.set_xy(10, y_start)
    pdf.set_font('helvetica', '', 11)
    pdf.cell(25, 8, 'Net Worth:', border=0)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(50, 8, f'${portfolio_net_worth:,.2f}', border=0)
    
    # Columna 2
    pdf.set_xy(100, y_start)
    pdf.set_font('helvetica', '', 11)
    pdf.cell(35, 8, 'Régimen Macro:', border=0)
    pdf.set_font('helvetica', 'B', 11)
    if 'Bull' in regime:
        pdf.set_text_color(39, 174, 96) # Verde
    elif 'Bear' in regime or 'Panic' in regime:
        pdf.set_text_color(192, 57, 43) # Rojo
    else:
        pdf.set_text_color(243, 156, 18) # Amarillo
    pdf.cell(60, 8, regime, border=0)
    
    pdf.set_text_color(0, 0, 0)
    y_next = y_start + 8
    
    # Fila 2, Columna 1
    pdf.set_xy(10, y_next)
    pdf.set_font('helvetica', '', 11)
    pdf.cell(35, 8, 'Liquidez (Cash):', border=0)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(50, 8, f'${total_cash:,.2f} ({cash_pct:.1f}%)', border=0)
    
    # Fila 2, Columna 2
    pdf.set_xy(100, y_next)
    pdf.set_font('helvetica', '', 11)
    pdf.cell(35, 8, 'Beta Ponderado:', border=0)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(40, 8, f'{beta_val:.2f}', border=0)
    
    pdf.set_y(y_next + 12)
    
    # 2. Análisis de Riesgo
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, 'Mandatos de Riesgo', ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font('helvetica', '', 11)
    pdf.set_text_color(0, 0, 0)
    
    req_cash_pct = dynamic_min_cash * 100
    pdf.cell(100, 8, f'Liquidez mínima exigida por modelo:', border=0)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(40, 8, f'{req_cash_pct:.1f}%', border=0, ln=True)
    
    pdf.set_font('helvetica', '', 11)
    # Validar todas las reglas de riesgo
    violations = []
    if cash_pct < req_cash_pct:
        violations.append("Efectivo Mínimo")
        
    if not df_enriched.empty:
        total_etf_weight = df_enriched[df_enriched['ticker'].isin(KNOWN_ETFS)]['weight'].sum()
        if total_etf_weight > MAX_ETF_WEIGHT:
            violations.append("Máx Total ETFs")
            
        for _, row in df_enriched.iterrows():
            if row['ticker'] not in KNOWN_ETFS and row['weight'] > MAX_STOCK_WEIGHT:
                violations.append(f"Máx por Acción ({row['ticker']})")

    if not violations:
        pdf.set_text_color(39, 174, 96)
        pdf.cell(0, 8, 'CUMPLE CON TODOS LOS MANDATOS', border=0, ln=True)
    else:
        pdf.set_text_color(192, 57, 43)
        pdf.set_font('helvetica', 'B', 11)
        pdf.cell(0, 8, 'VIOLACIONES DETECTADAS:', border=0, ln=True)
        pdf.set_font('helvetica', '', 11)
        for v in violations:
            pdf.multi_cell(0, 6, f"• {v}", border=0)
        
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)
    
    # 3. Top Posiciones
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, 'Inventario Consolidado', ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    if not df_enriched.empty:
        # Sort by weight
        df_sort = df_enriched.sort_values(by='weight', ascending=False)
        
        # Table Header
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(20, 8, 'Ticker', border=1, fill=True)
        pdf.cell(25, 8, 'Mercado ($)', border=1, fill=True, align='R')
        pdf.cell(20, 8, 'Peso (%)', border=1, fill=True, align='R')
        pdf.cell(25, 8, 'Retorno (%)', border=1, fill=True, align='R')
        pdf.cell(25, 8, 'Fair Value', border=1, fill=True, align='R')
        pdf.cell(25, 8, 'MOS (%)', border=1, fill=True, align='R')
        pdf.cell(50, 8, 'Señal Actual', border=1, fill=True, align='C')
        pdf.ln()
        
        # Table Body
        pdf.set_font('helvetica', '', 9)
        for _, row in df_sort.iterrows():
            ticker = str(row['ticker'])
            val = format_currency(row['market_value'])
            w_pct = format_percentage(row['weight'])
            ret_pct = format_percentage(row['unrealized_pl_pct'] / 100.0, decimals=2)
            
            fv_val = row.get('fair_value_final')
            fair_val_str = format_currency(fv_val)
            
            mos = row.get('margin_of_safety')
            mos_str = format_percentage(mos)
            
            signal = str(row.get('Signal', '-'))
            
            pdf.cell(20, 8, ticker, border=1)
            pdf.cell(25, 8, val, border=1, align='R')
            pdf.cell(20, 8, w_pct, border=1, align='R')
            
            # Color for return
            if row['unrealized_pl_pct'] >= 0:
                pdf.set_text_color(39, 174, 96)
            else:
                pdf.set_text_color(192, 57, 43)
            pdf.cell(25, 8, ret_pct, border=1, align='R')
            
            pdf.set_text_color(0, 0, 0)
            pdf.cell(25, 8, fair_val_str, border=1, align='R')
            
            # Color for MOS
            if pd.notnull(mos) and mos > 0.2:
                pdf.set_text_color(39, 174, 96)
            elif pd.notnull(mos) and mos < 0:
                pdf.set_text_color(192, 57, 43)
            pdf.cell(25, 8, mos_str, border=1, align='R')
            
            pdf.set_text_color(0, 0, 0)
            pdf.cell(50, 8, signal[:25], border=1, align='C')
            pdf.ln()
    else:
        pdf.set_font('helvetica', 'I', 11)
        pdf.cell(0, 10, 'Portafolio vacío.', ln=True)

    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
