from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, 
    Image, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
import pandas as pd

class PortfolioTearSheet:
    """
    Generador de Tear Sheets institucionales en PDF.
    """
    
    COLORS = {
        'primary': colors.HexColor('#1a1a2e'),
        'secondary': colors.HexColor('#16213e'),
        'accent_green': colors.HexColor('#2ecc71'),
        'accent_red': colors.HexColor('#e74c3c'),
        'accent_yellow': colors.HexColor('#f1c40f'),
        'text_white': colors.HexColor('#ecf0f1'),
        'text_gray': colors.HexColor('#95a5a6'),
        'bg_light': colors.HexColor('#f8f9fa')
    }
    
    def __init__(self, portfolio, metrics, risk_report, signal_results):
        self.portfolio = portfolio
        self.metrics = metrics
        self.risk_report = risk_report
        self.signals = signal_results
        self.styles = self._setup_styles()
    
    def _setup_styles(self):
        styles = getSampleStyleSheet()
        
        styles.add(ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=self.COLORS['primary'],
            spaceAfter=20,
            fontName='Helvetica-Bold'
        ))
        
        styles.add(ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=self.COLORS['text_gray'],
            spaceAfter=30
        ))
        
        styles.add(ParagraphStyle(
            'KPI_Value',
            parent=styles['Normal'],
            fontSize=24,
            textColor=self.COLORS['primary'],
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        ))
        
        styles.add(ParagraphStyle(
            'KPI_Label',
            parent=styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['text_gray'],
            alignment=TA_CENTER
        ))
        
        styles.add(ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=self.COLORS['primary'],
            spaceBefore=20,
            spaceAfter=10,
            fontName='Helvetica-Bold',
            borderColor=self.COLORS['accent_green'],
            borderWidth=2,
            borderPadding=5,
            leftIndent=0
        ))
        
        styles.add(ParagraphStyle(
            'Violation',
            parent=styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['accent_red'],
            backColor=colors.HexColor('#3b1c1c'),
            borderPadding=5
        ))
        
        return styles
    
    def generate(self, output_path: str = None) -> bytes:
        """Genera el PDF completo."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        story = []
        
        # ─── PÁGINA 1: RESUMEN EJECUTIVO ───
        story.extend(self._build_header())
        story.extend(self._build_kpi_grid())
        story.extend(self._build_risk_summary())
        story.extend(self._build_position_table())
        
        # ─── PÁGINA 2: ANÁLISIS DETALLADO ───
        story.append(PageBreak())
        story.extend(self._build_attribution())
        story.extend(self._build_signal_detail())
        story.extend(self._build_stress_test())
        
        # ─── PÁGINA 3: WATCHLIST Y OPORTUNIDADES ───
        story.append(PageBreak())
        story.extend(self._build_watchlist())
        story.extend(self._build_recommendations())
        
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes
    
    def _build_header(self):
        """Header con título y fecha."""
        return [
            Paragraph("PORTFOLIO TEAR SHEET", self.styles['Title']),
            Paragraph(
                f"Generado: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} | "
                f"Régimen: {self.risk_report.get('regime', 'N/A').replace('_', ' ').title()} | "
                f"Confianza: {self.risk_report.get('confidence', 'N/A')}",
                self.styles['Subtitle']
            ),
            Spacer(1, 0.2*inch)
        ]
    
    def _build_kpi_grid(self):
        """Grid de 4 KPIs principales."""
        kpi_data = [
            [
                Paragraph(f"${self.portfolio.nav:,.2f}", self.styles['KPI_Value']),
                Paragraph(f"${self.portfolio.cash:,.2f} ({self.portfolio.cash/self.portfolio.nav*100:.1f}%)" if self.portfolio.nav > 0 else "$0 (0%)", self.styles['KPI_Value']),
                Paragraph(f"{self.metrics.get('total_return', 0):.2%}", self.styles['KPI_Value']),
                Paragraph(f"{self.metrics.get('sharpe', 0):.2f}", self.styles['KPI_Value'])
            ],
            [
                Paragraph("NET WORTH", self.styles['KPI_Label']),
                Paragraph("LIQUIDEZ (CASH)", self.styles['KPI_Label']),
                Paragraph("RETORNO TOTAL", self.styles['KPI_Label']),
                Paragraph("SHARPE RATIO", self.styles['KPI_Label'])
            ]
        ]
        
        t = Table(kpi_data, colWidths=[1.5*inch]*4)
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), self.COLORS['bg_light']),
            ('BOX', (0, 0), (-1, -1), 1, self.COLORS['text_gray']),
        ]))
        
        return [t, Spacer(1, 0.3*inch)]
    
    def _build_risk_summary(self):
        """Sección de mandatos de riesgo."""
        elements = [Paragraph("MANDATOS DE RIESGO", self.styles['SectionHeader'])]
        
        if self.risk_report.get('compliant', True):
            elements.append(Paragraph(
                "✅ CUMPLE — Todos los parámetros de riesgo están dentro de los límites establecidos.",
                ParagraphStyle('Compliant', parent=self.styles['Normal'], 
                              textColor=self.COLORS['accent_green'],
                              backColor=colors.HexColor('#1e3d2f'),
                              borderPadding=8)
            ))
        else:
            violations = self.risk_report.get('violations', [])
            elements.append(Paragraph(
                f"🚨 VIOLACIONES DETECTADAS: {len(violations)}",
                self.styles['Violation']
            ))
            for v in violations:
                elements.append(Paragraph(
                    f"• <b>{v.get('type', 'Unknown')}</b>: {v.get('ticker', '')} "
                    f"({v.get('current', 0)*100:.1f}% > {v.get('limit', 0)*100:.0f}%) — {v.get('action', '')}",
                    ParagraphStyle('ViolationDetail', parent=self.styles['Normal'],
                                  textColor=self.COLORS['accent_red'],
                                  leftIndent=20)
                ))
        
        elements.append(Spacer(1, 0.2*inch))
        return elements
    
    def _build_position_table(self):
        """Tabla de inventario consolidado."""
        elements = [Paragraph("INVENTARIO CONSOLIDADO", self.styles['SectionHeader'])]
        
        headers = ['Ticker', 'Mercado ($)', 'Peso (%)', 'Retorno (%)', 
                   'Fair Value', 'MOS (%)', 'Señal', 'Kelly %']
        
        data = [headers]
        if hasattr(self.portfolio, 'positions') and not self.portfolio.positions.empty:
            for _, pos in self.portfolio.positions.iterrows():
                signal = next((s for s in self.signals if s.get('ticker') == pos['ticker']), {})
                
                row = [
                    pos['ticker'],
                    f"${pos.get('market_value', 0):,.0f}",
                    f"{pos.get('weight', 0)*100:.1f}%",
                    f"{pos.get('unrealized_pl_pct', 0):.2f}%",
                    f"${pos.get('fair_value', 0):,.2f}",
                    f"{pos.get('margin_of_safety', 0)*100:.1f}%",
                    signal.get('action', 'N/A'),
                    f"{signal.get('kelly_fraction', 0)*100:.1f}%"
                ]
                data.append(row)
        else:
            data.append(['No positions found', '', '', '', '', '', '', ''])
        
        t = Table(data, colWidths=[0.9*inch, 1.0*inch, 0.7*inch, 0.8*inch,
                                   0.9*inch, 0.7*inch, 1.0*inch, 0.7*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.COLORS['text_white']),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS['text_gray']),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.COLORS['bg_light'], colors.white]),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(t)
        return elements
    
    def _build_attribution(self):
        """Análisis de atribución Brinson."""
        return [Paragraph("ATRIBUCIÓN DE RENDIMIENTO", self.styles['SectionHeader'])]
    
    def _build_signal_detail(self):
        """Detalle de señales bayesianas."""
        return [Paragraph("SEÑALES BAYESIANAS", self.styles['SectionHeader'])]
    
    def _build_stress_test(self):
        """Escenarios de stress test."""
        return [Paragraph("TEST DE ESTRÉS", self.styles['SectionHeader'])]
    
    def _build_watchlist(self):
        """Watchlist con oportunidades."""
        return [Paragraph("RADAR DE OPORTUNIDADES", self.styles['SectionHeader'])]
    
    def _build_recommendations(self):
        """Recomendaciones finales."""
        return [Paragraph("RECOMENDACIONES", self.styles['SectionHeader'])]
