import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os

st.set_page_config(page_title="Custom Strategy Backtester", layout="wide")

SAVED_FILE = "strategies.json"

# Load saved strategies from disk
def load_saved_strategies():
    if os.path.exists(SAVED_FILE):
        try:
            with open(SAVED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# Save strategy to disk
def save_strategy_to_file(name, config):
    strategies = load_saved_strategies()
    strategies[name] = config
    with open(SAVED_FILE, "w") as f:
        json.dump(strategies, f, indent=4)

st.title("⚡ Dynamic Web Backtesting Lab")

# --- SIDEBAR: ASSET CONFIGURATION ---
st.sidebar.header("1. Asset Configuration")
market_type = st.sidebar.radio("Select Instrument", ["Nifty 50 Index (^NSEI)", "Custom Indian Stock (NSE)", "US Stock / Global", "Futures"])

if market_type == "Nifty 50 Index (^NSEI)":
    ticker = "^NSEI"
elif market_type == "Custom Indian Stock (NSE)":
    ticker = st.sidebar.text_input("Enter Ticker (e.g., RELIANCE.NS, TATAMOTORS.NS)", value="RELIANCE.NS")
elif market_type == "US Stock / Global":
    ticker = st.sidebar.text_input("Enter Ticker (e.g., AAPL, TSLA)", value="AAPL")
else:
    ticker = st.sidebar.text_input("Futures Ticker (e.g., GC=F Gold, NQ=F Nasdaq)", value="GC=F")

start_date = st.sidebar.date_input("Start Date", pd.to_datetime("2021-01-01"))
end_date = st.sidebar.date_input("End Date", pd.to_datetime("2026-01-01"))
capital = st.sidebar.number_input("Starting Capital (₹/$)", value=100000, step=10000)

# --- SIDEBAR: STRATEGY LOGIC BUILDER ---
st.sidebar.header("2. Dedicated Strategy Condition Engine")
strat_name = st.sidebar.text_input("Strategy Name", value="Nifty EMA-RSI Strategy")

st.sidebar.markdown("**Technical Indicators Period:**")
ema_period = st.sidebar.number_input("EMA Period", min_value=2, max_value=200, value=20)
rsi_period = st.sidebar.number_input("RSI Period", min_value=2, max_value=100, value=14)

st.sidebar.markdown("**Entry Rule (Pandas Logic):**")
entry_rule = st.sidebar.text_area("BUY Condition", value="(Close > EMA) and (RSI < 70)")

# --- SIDEBAR: SAVED STRATEGIES ---
st.sidebar.header("3. Saved Strategies")
if st.sidebar.button("💾 Save Strategy"):
    config = {
        "market_type": market_type,
        "ticker": ticker,
        "ema_period": int(ema_period),
        "rsi_period": int(rsi_period),
        "entry_rule": entry_rule,
        "capital": capital
    }
    save_strategy_to_file(strat_name, config)
    st.sidebar.success(f"Saved '{strat_name}' successfully!")

saved_strats = load_saved_strategies()
if saved_strats:
    selected_strat = st.sidebar.selectbox("Load Saved Strategy", list(saved_strats.keys()))
    if st.sidebar.button("📂 Load Selected Strategy"):
        loaded = saved_strats[selected_strat]
        st.info(f"Loaded: {selected_strat} | Ticker: {loaded['ticker']} | Rule: {loaded['entry_rule']}")

# --- FETCH DATA ---
@st.cache_data
def fetch_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

df = fetch_data(ticker, start_date, end_date)

if not df.empty and len(df) > 50:
    # 1. Native EMA Calculation
    df['EMA'] = df['Close'].ewm(span=ema_period, adjust=False).mean()
    
    # 2. Native RSI Calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=int(rsi_period)).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=int(rsi_period)).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 3. Dynamic Rule Evaluation
    try:
        df['Signal'] = df.eval(entry_rule).astype(int)
    except Exception as e:
        st.error(f"Error in Entry Rule Logic: {e}")
        df['Signal'] = 0

    df['Position'] = df['Signal'].shift(1).fillna(0)

    # 4. Returns & Equity Curve
    df['Market_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Position']
    df['Equity_Curve'] = capital * (1 + df['Strategy_Return'].fillna(0)).cumprod()

    # --- CHARTS ---
    st.subheader(f"Price & Indicator Analysis: {ticker}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Close / LTP", line=dict(color='gray')))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA'], name=f"EMA ({ema_period})"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Portfolio Equity Growth")
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=df.index, y=df['Equity_Curve'], name="Equity Curve", line=dict(color='green')))
    st.plotly_chart(fig_eq, use_container_width=True)

    # --- TRADE LOG TABLE ---
    st.subheader("📋 Trade Log Table")
    trades = []
    in_trade = False
    entry_date = None
    entry_price = 0
    qty = 0

    for i in range(1, len(df)):
        # Buy Trigger
        if df['Position'].iloc[i] == 1 and not in_trade:
            in_trade = True
            entry_date = df.index[i].strftime('%Y-%m-%d')
            entry_price = df['Close'].iloc[i]
            deployed = capital
            qty = deployed / entry_price
        
        # Exit Trigger
        elif df['Position'].iloc[i] == 0 and in_trade:
            in_trade = False
            exit_date = df.index[i].strftime('%Y-%m-%d')
            exit_price = df['Close'].iloc[i]
            pnl = (exit_price - entry_price) * qty
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            trades.append({
                "Entry Date": entry_date,
                "Entry LTP": round(entry_price, 2),
                "Amount Deployed": round(deployed, 2),
                "Exit Date": exit_date,
                "Exit LTP": round(exit_price, 2),
                "P&L (₹/$)": round(pnl, 2),
                "P&L (%)": f"{pnl_pct:.2f}%"
            })

    if trades:
        trade_df = pd.DataFrame(trades)
        st.dataframe(trade_df, use_container_width=True)
    else:
        st.info("No trades were executed with the current strategy conditions.")

else:
    st.error(f"Unable to load data for symbol '{ticker}'. Please check the symbol.")
