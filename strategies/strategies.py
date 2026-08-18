# strategies/strategies.py
"""Collection of trading strategies"""

import pandas as pd
from strategies.base_strategy import BaseStrategy
from indicators import indicators as ind


class SMACrossover(BaseStrategy):
    name = "SMA Crossover"
    description = "Buy when fast SMA crosses above slow SMA, sell on opposite."

    def generate_signals(self, df):
        fast = self.params.get("fast", 20)
        slow = self.params.get("slow", 50)
        df = ind.add_sma(df, fast)
        df = ind.add_sma(df, slow)
        df["Signal"] = 0
        cond_buy = (df[f"SMA_{fast}"] > df[f"SMA_{slow}"]) & \
                   (df[f"SMA_{fast}"].shift(1) <= df[f"SMA_{slow}"].shift(1))
        cond_sell = (df[f"SMA_{fast}"] < df[f"SMA_{slow}"]) & \
                    (df[f"SMA_{fast}"].shift(1) >= df[f"SMA_{slow}"].shift(1))
        df.loc[cond_buy, "Signal"] = 1
        df.loc[cond_sell, "Signal"] = -1
        return df


class EMACrossover(BaseStrategy):
    name = "EMA Crossover"
    description = "Buy when fast EMA crosses above slow EMA."

    def generate_signals(self, df):
        fast = self.params.get("fast", 12)
        slow = self.params.get("slow", 26)
        df = ind.add_ema(df, fast)
        df = ind.add_ema(df, slow)
        df["Signal"] = 0
        cond_buy = (df[f"EMA_{fast}"] > df[f"EMA_{slow}"]) & \
                   (df[f"EMA_{fast}"].shift(1) <= df[f"EMA_{slow}"].shift(1))
        cond_sell = (df[f"EMA_{fast}"] < df[f"EMA_{slow}"]) & \
                    (df[f"EMA_{fast}"].shift(1) >= df[f"EMA_{slow}"].shift(1))
        df.loc[cond_buy, "Signal"] = 1
        df.loc[cond_sell, "Signal"] = -1
        return df


class RSIStrategy(BaseStrategy):
    name = "RSI Oversold/Overbought"
    description = "Buy when RSI < oversold, sell when RSI > overbought."

    def generate_signals(self, df):
        period = self.params.get("period", 14)
        oversold = self.params.get("oversold", 30)
        overbought = self.params.get("overbought", 70)
        df = ind.add_rsi(df, period)
        df["Signal"] = 0
        df.loc[df[f"RSI_{period}"] < oversold, "Signal"] = 1
        df.loc[df[f"RSI_{period}"] > overbought, "Signal"] = -1
        return df


class MACDStrategy(BaseStrategy):
    name = "MACD Crossover"
    description = "Buy when MACD crosses above signal line."

    def generate_signals(self, df):
        df = ind.add_macd(df)
        df["Signal"] = 0
        cond_buy = (df["MACD"] > df["MACD_signal"]) & \
                   (df["MACD"].shift(1) <= df["MACD_signal"].shift(1))
        cond_sell = (df["MACD"] < df["MACD_signal"]) & \
                    (df["MACD"].shift(1) >= df["MACD_signal"].shift(1))
        df.loc[cond_buy, "Signal"] = 1
        df.loc[cond_sell, "Signal"] = -1
        return df


class BollingerStrategy(BaseStrategy):
    name = "Bollinger Bands"
    description = "Buy at lower band, sell at upper band."

    def generate_signals(self, df):
        period = self.params.get("period", 20)
        df = ind.add_bollinger(df, period)
        df["Signal"] = 0
        df.loc[df["Close"] < df["BB_low"], "Signal"] = 1
        df.loc[df["Close"] > df["BB_high"], "Signal"] = -1
        return df


class RSI_MACD_Combo(BaseStrategy):
    name = "RSI + MACD Combo"
    description = "Buy when RSI oversold AND MACD bullish crossover."

    def generate_signals(self, df):
        period = self.params.get("period", 14)
        df = ind.add_rsi(df, period)
        df = ind.add_macd(df)
        df["Signal"] = 0
        macd_bull = df["MACD"] > df["MACD_signal"]
        macd_bear = df["MACD"] < df["MACD_signal"]
        df.loc[(df[f"RSI_{period}"] < 40) & macd_bull, "Signal"] = 1
        df.loc[(df[f"RSI_{period}"] > 60) & macd_bear, "Signal"] = -1
        return df


# Registry of all strategies
STRATEGY_REGISTRY = {
    SMACrossover.name: SMACrossover,
    EMACrossover.name: EMACrossover,
    RSIStrategy.name: RSIStrategy,
    MACDStrategy.name: MACDStrategy,
    BollingerStrategy.name: BollingerStrategy,
    RSI_MACD_Combo.name: RSI_MACD_Combo,
}
