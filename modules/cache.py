import os
import sqlite3
import json
from datetime import datetime, timedelta
from portfolio_config import DATA_DIR

CACHE_DB_PATH = os.path.join(DATA_DIR, "price_cache.db")

class PriceCache:
    def __init__(self, db_path=CACHE_DB_PATH):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    ticker TEXT PRIMARY KEY,
                    data TEXT,
                    timestamp DATETIME
                )
            ''')
            conn.commit()

    def get(self, ticker: str, max_age_minutes: int = 15) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT data, timestamp FROM cache WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            
            if row:
                data_json, timestamp_str = row
                timestamp = datetime.fromisoformat(timestamp_str)
                if datetime.utcnow() - timestamp < timedelta(minutes=max_age_minutes):
                    return json.loads(data_json)
        return None

    def store(self, ticker: str, data: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "REPLACE INTO cache (ticker, data, timestamp) VALUES (?, ?, ?)",
                (ticker, json.dumps(data), datetime.utcnow().isoformat())
            )
            conn.commit()
