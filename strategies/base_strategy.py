# strategies/base_strategy.py
"""Base strategy class - all strategies inherit from this"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    name = "Base Strategy"
    description = "Base strategy class"

    def __init__(self, params: dict = None):
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, df):
        """
        Must return df with a 'Signal' column:
        1 = Buy/Enter Long, -1 = Sell/Exit, 0 = Hold
        """
        pass
