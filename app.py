import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json

st.set_page_config(page_title="Global Strategy Lab", layout="wide")

# Initialize Session State for Saved Strategies
if "saved_strategies" not in st.session_state:
    st.session_state["saved_strategies"] = {}

st.title("⚡ Multi-Market Strategy Lab & Backtester")

# --- SIDEBAR: ASSET & DATA CONFIGURATION ---
st.sidebar.header("1. Asset Configuration")
asset_class = st.sidebar.selectbox("Asset Class", ["Indian Stock/Index (NSE)", "US/Global Stock", "Futures"])

if asset_class == "Indian Stock/Index (NSE)":
    ticker = st.sidebar.text_input("Ticker Symbol (e.g. RELIANCE.NS, TATAMOTORS.NS, NIFTY50.NS)", value="RELIANCE.NS")
elif asset_class == "US/Global Stock":
    ticker = st.sidebar.text_input("Ticker Symbol (e.g. AAPL, TSLA, NVDA)", value="AAPL")
else:
    ticker = st.sidebar.text_input("Futures Ticker (e.g. GC=F Gold, NQ=F Nasdaq)", value="GC=F")

start_date = st.sidebar.date_input("Start Date", pd.to_datetime("2020-01-01"))
end_date = st.sidebar.date_input("End Date", pd.to_datetime("2026-01-01"))
capital = st.sidebar.number_input("Starting Capital ($/₹)", value=100000, step=10000)

# --- SIDEBAR: STRATEGY PARAMETERS ---
st.sidebar.header("2. Strategy Logic Settings")
strat_name = st.sidebar.text_input("Strategy Name", value="My Moving Average Crossover")
fast_ma = st.sidebar.number_input("Fast Moving Average (Days)", min_value=2, max_value=100, value=20)
slow_ma = st.sidebar.number_input("Slow Moving Average (Days)", min_value=5, max_value=200, value=50)

# --- SIDEBAR: SAVE & LOAD STRATEGIES ---
st.sidebar.header("3. Saved Strategies")
if st.sidebar.button("💾 Save Current Strategy"):
    st.session_state["saved_strategies"][strat_name] = {
        "asset_class": asset_class,
        "ticker": ticker,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "capital": capital
    }
    st.sidebar.success(f"Saved '{strat_name}' successfully!")

if st.session_state["saved_strategies"]:
    selected_saved = st.sidebar.selectbox("Load Saved Strategy", list(st.session_state["saved_strategies"].keys()))
    if st.sidebar.button("📂 Load Selected Strategy"):
        saved_data = st.session_state["saved_strategies"][selected_saved]
        st.info(f"Loaded '{selected_saved}' - Ticker: {saved_data['ticker']} | Fast MA: {saved_data['fast_ma']} | Slow MA: {saved_data['slow_ma']}")

# --- DATA FETCHING & BACKTEST ENGINE ---
@st.cache_data
def fetch_market_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

df = fetch_market_data(ticker, start_date, end_date)

if not df.empty:
    # Calculations
    df['Fast_MA'] = df['Close'].rolling(window=fast_ma).mean()
    df['Slow_MA'] = df['Close'].rolling(window=slow_ma).mean()
    
    # Signal Generation (Buy when Fast > Slow)
    df['Signal'] = np.where(df['Fast_MA'] > df['Slow_MA'], 1, 0)
    df['Position'] = df['Signal'].shift(1)
    
    # Returns Calculation
    df['Market_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Position']
    
    df['Equity_Curve'] = capital * (1 + df['Strategy_Return'].fillna(0)).cumprod()
    df['Buy_Hold_Curve'] = capital * (1 + df['Market_Return'].fillna(0)).cumprod()
    
    # Metrics
    total_strat_return = ((df['Equity_Curve'].iloc[-1] - capital) / capital) * 100
    total_market_return = ((df['Buy_Hold_Curve'].iloc[-1] - capital) / capital) * 100
    
    col1, col2 = st.columns(2)
    col1.metric(f"Strategy Return ({strat_name})", f"{total_strat_return:.2f}%")
    col2.metric("Buy & Hold Return", f"{total_market_return:.2f}%")
    
    # Price Chart
    st.subheader(f"Price & Indicators ({ticker})")
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Close Price", line=dict(color='gray', width=1)))
    fig_price.add_trace(go.Scatter(x=df.index, y=df['Fast_MA'], name=f"Fast MA ({fast_ma})"))
    fig_price.add_trace(go.Scatter(x=df.index, y=df['Slow_MA'], name=f"Slow MA ({slow_ma})"))
    st.plotly_chart(fig_price, use_container_width=True)
    
    # Equity Curve Chart
    st.subheader("Strategy Portfolio Value Over Time")
    fig_equity = go.Figure()
    fig_equity.add_trace(go.Scatter(x=df.index, y=df['Equity_Curve'], name="Strategy", line=dict(color='green')))
    fig_equity.add_trace(go.Scatter(x=df.index, y=df['Buy_Hold_Curve'], name="Buy & Hold", line=dict(color='blue', dash='dash')))
    st.plotly_chart(fig_equity, use_container_width=True)

else:
    st.error(f"Could not retrieve historical data for '{ticker}'. Please check the symbol.")
