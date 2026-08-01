import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.quant_engine import fetch_quant_data
from modules.signal_engine import BayesianSignal

tickers = ['AAPL', 'MSFT']
print("Testing fetch_quant_data...")
df = fetch_quant_data(tickers)
print(df.columns)
print(df[['ticker', 'composite_z', 'percentile']])

print("Testing BayesianSignal...")
signal_engine = BayesianSignal()
print(signal_engine.generate_signal(df.iloc[0]['composite_z'], 0.20))
print("Test passed.")
