# indicators/indicators.py
"""Technical indicators using the 'ta' library and custom logic"""

import pandas as pd
import numpy as np
from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange


def add_sma(df, period=20, col="Close"):
    df[f"SMA_{period}"] = SMAIndicator(df[col], window=period).sma_indicator()
    return df


def add_ema(df, period=20, col="Close"):
    df[f"EMA_{period}"] = EMAIndicator(df[col], window=period).ema_indicator()
    return df


def add_rsi(df, period=14, col="Close"):
    df[f"RSI_{period}"] = RSIIndicator(df[col], window=period).rsi()
    return df


def add_macd(df, col="Close"):
    macd = MACD(df[col])
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    df["MACD_hist"] = macd.macd_diff()
    return df


def add_bollinger(df, period=20, col="Close"):
    bb = BollingerBands(df[col], window=period)
    df["BB_high"] = bb.bollinger_hband()
    df["BB_low"] = bb.bollinger_lband()
    df["BB_mid"] = bb.bollinger_mavg()
    return df


def add_adx(df, period=14):
    adx = ADXIndicator(df["High"], df["Low"], df["Close"], window=period)
    df[f"ADX_{period}"] = adx.adx()
    return df


def add_stochastic(df, period=14):
    st = StochasticOscillator(df["High"], df["Low"], df["Close"], window=period)
    df["STOCH_k"] = st.stoch()
    df["STOCH_d"] = st.stoch_signal()
    return df


def add_atr(df, period=14):
    atr = AverageTrueRange(df["High"], df["Low"], df["Close"], window=period)
    df[f"ATR_{period}"] = atr.average_true_range()
    return df
