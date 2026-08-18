# backtest/engine.py
"""Core backtesting engine with performance metrics"""

import pandas as pd
import numpy as np


class BacktestEngine:
    def __init__(self, initial_capital=100000, position_size=1.0,
                 commission=0.0003, stop_loss=None, take_profit=None):
        self.initial_capital = initial_capital
        self.position_size = position_size  # fraction of capital
        self.commission = commission        # 0.03% default
        self.stop_loss = stop_loss          # e.g. 0.05 for 5%
        self.take_profit = take_profit

    def run(self, df):
        df = df.copy()
        capital = self.initial_capital
        position = 0
        entry_price = 0
        trades = []
        equity_curve = []

        for i in range(len(df)):
            price = df["Close"].iloc[i]
            signal = df["Signal"].iloc[i]
            date = df.index[i]

            # Check SL/TP if in position
            if position > 0:
                change = (price - entry_price) / entry_price
                exit_now = False
                reason = ""
                if self.stop_loss and change <= -self.stop_loss:
                    exit_now, reason = True, "Stop Loss"
                elif self.take_profit and change >= self.take_profit:
                    exit_now, reason = True, "Take Profit"
                elif signal == -1:
                    exit_now, reason = True, "Signal"

                if exit_now:
                    proceeds = position * price * (1 - self.commission)
                    capital += proceeds
                    pnl = proceeds - (position * entry_price)
                    trades[-1].update({
                        "Exit Date": date, "Exit Price": round(price, 2),
                        "PnL": round(pnl, 2),
                        "Return %": round(change * 100, 2),
                        "Exit Reason": reason,
                    })
                    position = 0

            # Entry
            if signal == 1 and position == 0:
                invest = capital * self.position_size
                position = invest / (price * (1 + self.commission))
                capital -= position * price * (1 + self.commission)
                entry_price = price
                trades.append({
                    "Entry Date": date, "Entry Price": round(price, 2),
                    "Exit Date": None, "Exit Price": None,
                    "PnL": None, "Return %": None, "Exit Reason": None,
                })

            total_value = capital + (position * price)
            equity_curve.append({"Date": date, "Equity": total_value})

        # Close open position at end
        if position > 0:
            price = df["Close"].iloc[-1]
            proceeds = position * price * (1 - self.commission)
            capital += proceeds
            change = (price - entry_price) / entry_price
            trades[-1].update({
                "Exit Date": df.index[-1], "Exit Price": round(price, 2),
                "PnL": round(proceeds - (position * entry_price), 2),
                "Return %": round(change * 100, 2),
                "Exit Reason": "End of Data",
            })

        equity_df = pd.DataFrame(equity_curve).set_index("Date")
        trades_df = pd.DataFrame([t for t in trades if t["Exit Date"] is not None])
        metrics = self._calc_metrics(equity_df, trades_df)
        return {"equity": equity_df, "trades": trades_df, "metrics": metrics}

    def _calc_metrics(self, equity_df, trades_df):
        if equity_df.empty:
            return {}

        final_equity = equity_df["Equity"].iloc[-1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100

        # Drawdown
        rolling_max = equity_df["Equity"].cummax()
        drawdown = (equity_df["Equity"] - rolling_max) / rolling_max
        max_dd = drawdown.min() * 100

        # Returns
        rets = equity_df["Equity"].pct_change().dropna()
        sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() != 0 else 0

        # Trade stats
        num_trades = len(trades_df)
        wins = trades_df[trades_df["PnL"] > 0] if num_trades else pd.DataFrame()
        losses = trades_df[trades_df["PnL"] <= 0] if num_trades else pd.DataFrame()
        win_rate = (len(wins) / num_trades * 100) if num_trades else 0
        avg_win = wins["Return %"].mean() if len(wins) else 0
        avg_loss = losses["Return %"].mean() if len(losses) else 0
        profit_factor = (wins["PnL"].sum() / abs(losses["PnL"].sum())) \
            if len(losses) and losses["PnL"].sum() != 0 else 0

        return {
            "Total Return %": round(total_return, 2),
            "Final Equity": round(final_equity, 2),
            "Max Drawdown %": round(max_dd, 2),
            "Sharpe Ratio": round(sharpe, 2),
            "Total Trades": num_trades,
            "Win Rate %": round(win_rate, 2),
            "Avg Win %": round(avg_win, 2),
            "Avg Loss %": round(avg_loss, 2),
            "Profit Factor": round(profit_factor, 2),
        }
