import asyncio
import aiohttp
import pandas as pd
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class ScanResult:
    ticker: str
    composite_score: float
    signal: str
    mos: float
    trend_score: float
    quality_score: float
    prob_success: float
    kelly_fraction: float
    market_cap: float
    sector: str

class AsyncScanner:
    """
    Scanner asíncrono que evalúa universo completo (S&P 500, Russell 2000, etc.)
    """
    
    UNIVERSES = {
        'sp500': 'data/sp500_constituents.csv',
        'russell2000': 'data/russell2000.csv',
        'nasdaq100': 'data/nasdaq100.csv',
        'watchlist': None  # Usa watchlist de la DB
    }
    
    def __init__(self, signal_engine, risk_manager, max_concurrent=20):
        self.signal_engine = signal_engine
        self.risk_manager = risk_manager
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _fetch_single(self, ticker: str, session: aiohttp.ClientSession) -> dict:
        """Fetch asíncrono de un ticker."""
        async with self.semaphore:
            # Usar yfinance de forma no bloqueante
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,  # Default executor
                self._fetch_sync,
                ticker
            )
    
    def _fetch_sync(self, ticker: str) -> dict:
        """Wrapper síncrono para yfinance."""
        from modules.quant_engine import fetch_quant_data
        df = fetch_quant_data([ticker])
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    
    async def scan_universe(self, universe_name: str = 'sp500') -> List[ScanResult]:
        """Escanear universo completo."""
        # Cargar tickers
        if universe_name == 'watchlist':
            from modules.db import SessionLocal, WatchlistItem
            with SessionLocal() as session:
                tickers = [w.ticker for w in session.query(WatchlistItem).all()]
        else:
            try:
                df = pd.read_csv(self.UNIVERSES[universe_name])
                tickers = df['ticker'].tolist()
            except FileNotFoundError:
                tickers = ['AAPL', 'MSFT', 'GOOGL'] # Fallback for now
        
        # Fetch asíncrono
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_single(t, session) for t in tickers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtrar errores y procesar
        valid_results = []
        for ticker, data in zip(tickers, results):
            if isinstance(data, Exception) or data is None:
                continue
            
            # Calcular señal
            signal = self.signal_engine.generate_signal(
                ticker=ticker,
                current_price=data['current_price'],
                mos=data.get('margin_of_safety', 0),
                trend_score=0,  # Calcular de data
                quality_score=0,  # Calcular de data
                risk_score=0,
                portfolio_nav=100000,  # Placeholder
                current_weight=0,
                max_weight=0.10,
                available_cash=10000
            )
            
            valid_results.append(ScanResult(
                ticker=ticker,
                composite_score=signal.probability,
                signal=signal.action,
                mos=data.get('margin_of_safety', 0),
                trend_score=0,
                quality_score=0,
                prob_success=signal.probability,
                kelly_fraction=signal.kelly_fraction,
                market_cap=data.get('market_cap', 0),
                sector='Unknown'
            ))
        
        # Ordenar por score compuesto
        valid_results.sort(key=lambda x: x.composite_score, reverse=True)
        return valid_results
    
    def get_top_opportunities(self, n: int = 20) -> pd.DataFrame:
        """Wrapper síncrono para uso en Streamlit."""
        results = asyncio.run(self.scan_universe())
        return pd.DataFrame([vars(r) for r in results[:n]])
