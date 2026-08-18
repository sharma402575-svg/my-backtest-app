# 📊 Indian Market Pro-Quant Backtesting Application

An interactive, high-performance backtesting engine built with **Streamlit**, **Pandas**, and **Plotly** designed specifically for quantitative analysis in the Indian Stock Markets (NSE/BSE). Run, analyze, and save multi-strategy configurations dynamically.

## 🚀 Key Features

* **Multi-Sector Capabilities:** Supports NSE & BSE stocks, index benchmarks (Nifty 50, Nifty Bank), and customized user-defined tickers.
* **Pre-engineered Strategies:** 
  * Moving Average (EMA/SMA) Crossovers
  * RSI (Relative Strength Index) Mean-Reversion
  * MACD (Moving Average Convergence Divergence) Momentum Crosses
* **Multi-Timeframe Analysis:** Supports Daily (`1d`), Hourly (`1h`), and Intraday (`15m`, `5m`) intervals via `yfinance`.
* **Institutional Metrics Engine:** Calculates CAGR, Sharpe Ratio, Max Drawdown (Risk profile), Trade Counts, and overall Win Rates.
* **Local Database Storage:** Features an integrated SQLite engine that records your chosen strategy's results so you can review previous setups anytime.
* **Interactive Visualization:** Powered by Plotly, supporting zooming, panning, tracking buy/sell triggers, and portfolio value curves.

## 📦 How to Install and Run Locally

Ensure you have **Python 3.8+** installed on your workstation.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR-USERNAME/indian-market-backtester.git
   cd indian-market-backtester
