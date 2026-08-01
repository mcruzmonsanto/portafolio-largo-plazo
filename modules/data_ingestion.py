import os
import requests
import yfinance as yf
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime
import logging
from modules.cache import PriceCache

logger = logging.getLogger(__name__)

@dataclass
class PriceQuote:
    ticker: str
    price: float
    market_cap: float
    target_price: float
    eps: float
    growth: float
    roe: float
    op_margin: float
    debt_equity: float
    beta: float
    source: str
    confidence: float

class YFinanceProvider:
    def fetch(self, ticker: str) -> dict:
        info = yf.Ticker(ticker).info
        if not info:
            raise ValueError(f"No data from yfinance for {ticker}")
            
        growth = info.get('revenueGrowth')
        if growth is None:
            growth = info.get('earningsGrowth')
        if growth is None:
            growth = 0.05
            
        return {
            'ticker': ticker,
            'price': info.get('currentPrice') or info.get('regularMarketPrice') or 0.0,
            'market_cap': info.get('marketCap') or 0.0,
            'target_price': info.get('targetMeanPrice'),
            'eps': info.get('trailingEps'),
            'growth': growth,
            'roe': info.get('returnOnEquity'),
            'op_margin': info.get('operatingMargins') or info.get('profitMargins'),
            'debt_equity': info.get('debtToEquity'),
            'beta': info.get('beta', 1.0),
            'source': 'yfinance',
            'confidence': 0.8
        }

class AlphaVantageProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def fetch(self, ticker: str) -> dict:
        if not self.api_key:
            raise ValueError("No API key for AlphaVantage")
        # In a real implementation, we would make a request to GLOBAL_QUOTE and OVERVIEW
        # For now, we simulate missing data to fall back to yfinance, 
        # or implement a skeleton that fails fast if the key is missing.
        raise NotImplementedError("AlphaVantage integration pending full API payload structure.")

class PolygonProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def fetch(self, ticker: str) -> dict:
        if not self.api_key:
            raise ValueError("No API key for Polygon")
        raise NotImplementedError("Polygon integration pending full API payload structure.")

class DataProvider:
    def __init__(self):
        # We fetch keys from OS ENV. In Streamlit Cloud these are configured in secrets.
        self.providers = {
            'polygon': PolygonProvider(os.environ.get('POLYGON_API_KEY')),
            'alpha_vantage': AlphaVantageProvider(os.environ.get('ALPHAVANTAGE_API_KEY')),
            'yfinance': YFinanceProvider()  # Fallback
        }
        self.cache = PriceCache()
    
    def get_quote(self, ticker: str) -> PriceQuote:
        cached = self.cache.get(ticker, max_age_minutes=15)
        if cached:
            return PriceQuote(**cached)
            
        for name, provider in self.providers.items():
            try:
                data = provider.fetch(ticker)
                if self._validate_quote(data):
                    self.cache.store(ticker, data)
                    return PriceQuote(**data)
            except Exception as e:
                logger.debug(f"{name} failed for {ticker}: {e}")
                continue
                
        # If all fail, return empty dict or default values
        return PriceQuote(
            ticker=ticker, price=0.0, market_cap=0.0, target_price=None,
            eps=None, growth=0.05, roe=None, op_margin=None, debt_equity=None, beta=1.0,
            source="none", confidence=0.0
        )
        
    def _validate_quote(self, data: dict) -> bool:
        if data.get('price', 0) <= 0:
            return False
        return True
