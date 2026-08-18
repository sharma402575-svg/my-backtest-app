import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os

st.set_page_config(page_title="Versatile Multi-Market Lab", layout="wide")

SAVED_FILE = "strategies.json"

def load_saved_strategies():
    if os.path.exists(SAVED_FILE):
        try:
            with open(SAVED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_strategy_to_file(name, config):
    strategies = load_saved_strategies()
    strategies[name] = config
    with open(SAVED_FILE, "w") as f:
        json.dump(strategies, f, indent=4)

st.title("⚡ Versatile Multi-Market Strategy Lab")

# --- SIDEBAR: ASSET SELECTION ---
st.sidebar.header("1. Asset Configuration")
market_type = st.sidebar.radio("Select Asset Type", ["Nifty 50 Index (^NSEI)", "Custom Indian Stock (NSE)", "US Stock / Global", "Futures"])

if market_type == "Nifty 50 Index (^NSEI)":
    ticker = "^NSEI"
elif market_type == "Custom Indian Stock (NSE)":
    ticker = st.sidebar.text_input("NSE Ticker (e.g. RELIANCE.NS, TATAMOTORS.NS)", value="RELIANCE.NS")
elif market_type == "US Stock / Global":
    ticker = st.sidebar.text_input("Global Ticker (e.g. AAPL, TSLA)", value="AAPL")
else:
    ticker = st.sidebar.text_input("Futures Ticker (e.g. GC=F, NQ=F)", value="GC=F")

start_date = st.sidebar.date_input("Start Date", pd.to_datetime("2021-01-01"))
end_date = st.sidebar.date_input("End Date", pd.to_datetime("2026-01-01"))
capital = st.sidebar.number_input("Starting Capital (₹/$)", value=100000, step=10000)

# --- SIDEBAR: VERSATILE INDICATOR BUILDER ---
st.sidebar.header("2. Indicator Configurator")
sma_fast_p = st.sidebar.number_input("Fast SMA Period", value=10)
sma_slow_p = st.sidebar.number_input("Slow SMA Period", value=50)
ema_p = st.sidebar.number_input("EMA Period", value=20)
rsi_p = st.sidebar.number_input("RSI Period", value=14)

st.sidebar.header("3. Dynamic Rules (Any Formula)")
entry_rule = st.sidebar.text_area("BUY Entry Logic", value="(SMA_Fast > SMA_Slow) and (RSI < 70)")
exit_rule = st.sidebar.text_area("SELL / Exit Logic", value="(SMA_Fast < SMA_Slow) or (RSI > 80)")

# --- SIDEBAR: STRATEGY PERSISTENCE ---
st.sidebar.header("4. Strategy Storage")
strat_name = st.sidebar.text_input("Strategy Name", value="Multi-Indicator Setup")
if st.sidebar.button("💾 Save Strategy"):
    config = {
        "market_type": market_type, "ticker": ticker,
        "sma_fast": int(sma_fast_p), "sma_slow": int(sma_slow_p),
        "ema": int(ema_p), "rsi": int(rsi_p),
        "entry_rule": entry_rule, "exit_rule": exit_rule, "capital": capital
    }
    save_strategy_to_file(strat_name, config)
    st.sidebar.success(f"Saved '{strat_name}' successfully!")

saved_strats = load_saved_strategies()
if saved_strats:
    selected_strat = st.sidebar.selectbox("Load Saved Setup", list(saved_strats.keys()))
    if st.sidebar.button("📂 Load Selected Setup"):
        loaded = saved_strats[selected_strat]
        st.info(f"Loaded: {selected_strat} | Rule: {loaded['entry_rule']}")

# --- DATA FETCHING & MULTIINDEX FIX ---
@st.cache_data
def fetch_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end)
    if isinstance(data.columns, pd.MultiIndex):
        try:
            data.columns = data.columns.droplevel(1)
        except Exception:
            data.columns = data.columns.get_level_values(0)
    return data

df = fetch_data(ticker, start_date, end_date)

if not df.empty and len(df) > 50:
    # --- VERSATILE TECHNICAL CALCULATIONS ---
    df['SMA_Fast'] = df['Close'].rolling(window=int(sma_fast_p)).mean()
    df['SMA_Slow'] = df['Close'].rolling(window=int(sma_slow_p)).mean()
    df['EMA'] = df['Close'].ewm(span=int(ema_p), adjust=False).mean()
    
    # RSI calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=int(rsi_p)).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=int(rsi_p)).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD Calculation
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # --- DYNAMIC EVALUATION ENGINE ---
    try:
        df['Buy_Cond'] = df.eval(entry_rule).astype(int)
        df['Exit_Cond'] = df.eval(exit_rule).astype(int)
    except Exception as e:
        st.error(f"Logic Evaluation Error: {e}")
        df['Buy_Cond'] = 0
        df['Exit_Cond'] = 0

    # Simulation loop for custom position rules
    positions = []
    current_pos = 0
    for i in range(len(df)):
        if current_pos == 0:
            if df['Buy_Cond'].iloc[i] == 1:
                current_pos = 1
        elif current_pos == 1:
            if df['Exit_Cond'].iloc[i] == 1:
                current_pos = 0
        positions.append(current_pos)

    df['Position'] = pd.Series(positions, index=df.index).shift(1).fillna(0)
    df['Market_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Position']
    df['Equity_Curve'] = capital * (1 + df['Strategy_Return'].fillna(0)).cumprod()

    # --- TRADE LOG & METRICS GENERATION ---
    trades = []
    in_trade = False
    entry_date = None
    entry_price = 0
    cum_pnl = 0

    for i in range(1, len(df)):
        if df['Position'].iloc[i] == 1 and not in_trade:
            in_trade = True
            entry_date = df.index[i]
            entry_price = df['Close'].iloc[i]
            deployed = capital
            qty = deployed / entry_price
        
        elif df['Position'].iloc[i] == 0 and in_trade:
            in_trade = False
            exit_date = df.index[i]
            exit_price = df['Close'].iloc[i]
            net_pnl = (exit_price - entry_price) * qty
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            cum_pnl += net_pnl
            duration = (exit_date - entry_date).days

            trades.append({
                "Entry Date": entry_date.strftime('%Y-%m-%d'),
                "Entry LTP": round(entry_price, 2),
                "Exit Date": exit_date.strftime('%Y-%m-%d'),
                "Exit LTP": round(exit_price, 2),
                "Duration (Days)": duration,
                "Amount Deployed": round(deployed, 2),
                "Net P&L (₹/$)": round(net_pnl, 2),
                "P&L (%)": round(pnl_pct, 2),
                "Cum. P&L": round(cum_pnl, 2)
            })

    # --- TOP PERFORMANCE DASHBOARD ---
    st.subheader("📊 Performance Summary Dashboard")
    if trades:
        trade_df = pd.DataFrame(trades)
        total_trades = len(trade_df)
        winning_trades = len(trade_df[trade_df['Net P&L (₹/$)'] > 0])
        win_rate = (winning_trades / total_trades) * 100
        
        total_strat_return = ((df['Equity_Curve'].iloc[-1] - capital) / capital) * 100
        
        # Drawdown calculation
        cummax = df['Equity_Curve'].cummax()
        drawdown = ((df['Equity_Curve'] - cummax) / cummax) * 100
        max_drawdown = drawdown.min()

        gross_profit = trade_df[trade_df['Net P&L (₹/$)'] > 0]['Net P&L (₹/$)'].sum()
        gross_loss = abs(trade_df[trade_df['Net P&L (₹/$)'] < 0]['Net P&L (₹/$)'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss != 0 else np.nan

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Strategy Return", f"{total_strat_return:.2f}%")
        m2.metric("Win Rate", f"{win_rate:.1f}%")
        m3.metric("Max Drawdown", f"{max_drawdown:.2f}%")
        m4.metric("Profit Factor", f"{profit_factor:.2f}" if not np.isnan(profit_factor) else "N/A")
        m5.metric("Total Trades", f"{total_trades}")
    else:
        st.warning("No trades executed based on current Entry/Exit conditions.")

    # --- CHARTS SECTION ---
    st.subheader(f"Price & Indicator Analysis: {ticker}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Close Price / LTP", line=dict(color='black')))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Fast'], name=f"Fast SMA ({sma_fast_p})"))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Slow'], name=f"Slow SMA ({sma_slow_p})"))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA'], name=f"EMA ({ema_p})"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Portfolio Equity Curve Growth")
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=df.index, y=df['Equity_Curve'], name="Strategy Equity", line=dict(color='green')))
    st.plotly_chart(fig_eq, use_container_width=True)

    # --- TRADE LOG TABLE ---
    st.subheader("📋 Trade Log Table")
    if trades:
        st.dataframe(trade_df, use_container_width=True)

else:
    st.error(f"Unable to load data for symbol '{ticker}'. Make sure the ticker name is valid.")
    
