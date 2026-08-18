# data/data_loader.py
"""Fetch Indian market data via yfinance"""

import yfinance as yf
import pandas as pd
import streamlit as st


@st.cache_data(ttl=3600)
def fetch_data(symbol, interval="1d", period="2y", start=None, end=None):
    """Fetch OHLCV data for a symbol."""
    try:
        ticker = yf.Ticker(symbol)
        if start and end:
            df = ticker.history(interval=interval, start=start, end=end)
        else:
            df = ticker.history(interval=interval, period=period)

        if df.empty:
            return None

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)
        return df
    except Exception as e:
        st.error(f"Error fetching {symbol}: {e}")
        return None
