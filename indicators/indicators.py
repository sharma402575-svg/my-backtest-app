# indicators/indicators.py
"""Technical indicators implemented with pandas/numpy – no external TA library needed."""

import pandas as pd
import numpy as np


def add_sma(df, period=20, col="Close"):
    df[f"SMA_{period}"] = df[col].rolling(window=period, min_periods=period).mean()
    return df


def add_ema(df, period=20, col="Close"):
    df[f"EMA_{period}"] = df[col].ewm(span=period, adjust=False).mean()
    return df


def add_rsi(df, period=14, col="Close"):
    delta = df[col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    df[f"RSI_{period}"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df, col="Close", fast=12, slow=26, signal=9):
    ema_fast = df[col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[col].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line

    df["MACD"] = macd_line
    df["MACD_signal"] = signal_line
    df["MACD_hist"] = hist
    return df


def add_bollinger(df, period=20, col="Close", num_std=2):
    mid = df[col].rolling(window=period).mean()
    std = df[col].rolling(window=period).std()
    df["BB_high"] = mid + (std * num_std)
    df["BB_low"] = mid - (std * num_std)
    df["BB_mid"] = mid
    return df


def add_adx(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1/period, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, min_periods=period).mean()
    df[f"ADX_{period}"] = adx
    return df


def add_stochastic(df, period=14, smooth_k=3):
    low_min = df["Low"].rolling(window=period).min()
    high_max = df["High"].rolling(window=period).max()
    k = 100 * (df["Close"] - low_min) / (high_max - low_min)
    df["STOCH_k"] = k.rolling(window=smooth_k).mean()
    df["STOCH_d"] = df["STOCH_k"].rolling(window=3).mean()
    return df


def add_atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df[f"ATR_{period}"] = tr.ewm(alpha=1/period, min_periods=period).mean()
    return df
