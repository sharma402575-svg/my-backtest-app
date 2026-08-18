import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
from datetime import datetime, timedelta

# --- DATABASE SETUP ---
DB_FILE = "backtest_results.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            strategy_name TEXT,
            ticker TEXT,
            timeframe TEXT,
            total_return REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            win_rate REAL,
            total_trades INTEGER,
            parameters TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_strategy_to_db(strat_data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO saved_strategies 
        (timestamp, strategy_name, ticker, timeframe, total_return, sharpe_ratio, max_drawdown, win_rate, total_trades, parameters)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        strat_data['strategy_name'],
        strat_data['ticker'],
        strat_data['timeframe'],
        strat_data['total_return'],
        strat_data['sharpe_ratio'],
        strat_data['max_drawdown'],
        strat_data['win_rate'],
        strat_data['total_trades'],
        str(strat_data['parameters'])
    ))
    conn.commit()
    conn.close()

def get_saved_strategies():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM saved_strategies ORDER BY id DESC", conn)
    conn.close()
    return df

def delete_saved_strategy(id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_strategies WHERE id = ?", (id,))
    conn.commit()
    conn.close()

# --- INDIAN MARKET SECTOR PRESETS ---
INDIAN_SECTORS = {
    "Indices": ["^NSEI", "^NSEBANK", "NIFTY_MIDCAP_50.NS"],
    "IT Sector": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "Banking & Finance": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "Auto Sector": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BHARATFORG.NS", "EICHERMOT.NS"],
    "Energy & Resources": ["RELIANCE.NS", "ONGC.NS", "POWERGRID.NS", "NTPC.NS", "COALINDIA.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS"],
    "Custom Ticker": []
}

# --- STRATEGIES ---
def apply_ma_crossover(df, fast_period, slow_period):
    df['Fast_MA'] = df['Close'].rolling(window=fast_period).mean()
    df['Slow_MA'] = df['Close'].rolling(window=slow_period).mean()
    df['Signal'] = 0
    df.iloc[fast_period:, df.columns.get_loc('Signal')] = np.where(
        df['Fast_MA'].iloc[fast_period:] > df['Slow_MA'].iloc[fast_period:], 1, -1
    )
    df['Position'] = df['Signal'].shift(1)
    return df

def apply_rsi_strategy(df, period, oversold, overbought):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['Signal'] = 0
    # Buy when oversold, Sell when overbought
    df.loc[df['RSI'] < oversold, 'Signal'] = 1
    df.loc[df['RSI'] > overbought, 'Signal'] = -1
    df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
    df['Position'] = df['Signal'].shift(1)
    return df

def apply_macd_strategy(df, fast, slow, signal):
    fast_ema = df['Close'].ewm(span=fast, adjust=False).mean()
    slow_ema = df['Close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = fast_ema - slow_ema
    df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    
    df['Signal'] = np.where(df['MACD'] > df['MACD_Signal'], 1, -1)
    df['Position'] = df['Signal'].shift(1)
    return df

# --- PERFORMANCE ENGINE ---
def evaluate_performance(df, initial_capital=100000):
    df = df.dropna().copy()
    if len(df) == 0:
        return None, None
        
    df['Market_Returns'] = df['Close'].pct_change()
    df['Strategy_Returns'] = df['Market_Returns'] * df['Position']
    df['Cum_Strategy_Returns'] = (1 + df['Strategy_Returns'].fillna(0)).cumprod()
    df['Cum_Market_Returns'] = (1 + df['Market_Returns'].fillna(0)).cumprod()
    
    df['Portfolio_Value'] = df['Cum_Strategy_Returns'] * initial_capital

    # Calculate Drawdown
    df['Peak'] = df['Portfolio_Value'].cummax()
    df['Drawdown'] = (df['Portfolio_Value'] - df['Peak']) / df['Peak']
    max_dd = df['Drawdown'].min()

    # Calculate Trade Metrics
    df['Trade_Signal'] = df['Position'].diff()
    trades = df[df['Trade_Signal'] != 0]
    total_trades = len(trades)
    
    # Calculate Win Rate
    trade_returns = df['Strategy_Returns'][df['Trade_Signal'] != 0]
    winning_trades = len(trade_returns[trade_returns > 0])
    win_rate = (winning_trades / total_trades) if total_trades > 0 else 0

    # Sharpe Ratio (Assuming 5% Risk Free Rate in India)
    rf_daily = 0.05 / 252
    excess_returns = df['Strategy_Returns'] - rf_daily
    sharpe = np.sqrt(252) * (excess_returns.mean() / (excess_returns.std() + 1e-10))

    total_return = (df['Portfolio_Value'].iloc[-1] - initial_capital) / initial_capital

    metrics = {
        "Total Return (%)": round(total_return * 100, 2),
        "Market Return (%)": round((df['Cum_Market_Returns'].iloc[-1] - 1) * 100, 2),
        "Sharpe Ratio": round(sharpe, 2),
        "Max Drawdown (%)": round(max_dd * 100, 2),
        "Total Trades": total_trades,
        "Win Rate (%)": round(win_rate * 100, 2),
        "Final Value (₹)": f"₹{df['Portfolio_Value'].iloc[-1]:,.2f}"
    }
    
    return metrics, df

# --- STREAMLIT UI ---
st.set_page_config(page_title="Pro-Quant Backtester (Indian Market)", layout="wide")
init_db()

st.title("📊 Pro-Quant Backtester (Indian Market)")
st.caption("Perform enterprise-grade historical backtesting on NSE/BSE Index & Stocks.")

# Sidebar Configuration
st.sidebar.header("🔧 Configuration")

# 1. Sector & Ticker Selection
sector = st.sidebar.selectbox("Choose Sector / Universe", list(INDIAN_SECTORS.keys()))
if sector == "Custom Ticker":
    ticker_input = st.sidebar.text_input("Enter NSE/BSE Ticker (e.g., RELIANCE.NS, INFIBEAM.BO)", "RELIANCE.NS")
    ticker = ticker_input.upper()
else:
    ticker = st.sidebar.selectbox("Select Stock", INDIAN_SECTORS[sector])

# 2. Timeframe & Date
timeframe = st.sidebar.selectbox("Select Timeframe", ["1d", "1h", "15m", "5m"])
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("End Date", datetime.now())

# 3. Strategy Setup
st.sidebar.header("🎯 Strategy & Parameters")
strategy_choice = st.sidebar.selectbox("Choose Strategy", ["Moving Average Crossover", "RSI Mean Reversion", "MACD Crossover"])

params = {}
if strategy_choice == "Moving Average Crossover":
    params['fast_period'] = st.sidebar.slider("Fast MA Period", 5, 50, 9)
    params['slow_period'] = st.sidebar.slider("Slow MA Period", 20, 200, 21)
elif strategy_choice == "RSI Mean Reversion":
    params['period'] = st.sidebar.slider("RSI Period", 5, 30, 14)
    params['oversold'] = st.sidebar.slider("Oversold Level (Buy)", 10, 40, 30)
    params['overbought'] = st.sidebar.slider("Overbought Level (Sell)", 60, 90, 70)
elif strategy_choice == "MACD Crossover":
    params['fast'] = st.sidebar.slider("Fast EMA", 5, 30, 12)
    params['slow'] = st.sidebar.slider("Slow EMA", 20, 100, 26)
    params['signal'] = st.sidebar.slider("Signal Line", 5, 20, 9)

initial_capital = st.sidebar.number_input("Initial Capital (INR)", value=100000, step=10000)

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Backtest Engine", "💾 Saved Strategies", "📝 Guide & Docs"])

with tab1:
    if st.button("▶ Run Backtest", use_container_width=True):
        with st.spinner(f"Fetching historical data for {ticker}..."):
            try:
                # Fetch Data
                df = yf.download(ticker, start=start_date, end=end_date, interval=timeframe)
                
                if df.empty:
                    st.error("No data found! Ensure you used the correct suffix (e.g., .NS for National Stock Exchange).")
                else:
                    # Apply Strategy
                    if strategy_choice == "Moving Average Crossover":
                        df = apply_ma_crossover(df, params['fast_period'], params['slow_period'])
                    elif strategy_choice == "RSI Mean Reversion":
                        df = apply_rsi_strategy(df, params['period'], params['oversold'], params['overbought'])
                    elif strategy_choice == "MACD Crossover":
                        df = apply_macd_strategy(df, params['fast'], params['slow'], params['signal'])

                    # Run Metrics Evaluation
                    metrics, result_df = evaluate_performance(df, initial_capital)

                    if metrics is None:
                        st.error("Strategy couldn't generate trades. Try widening the Date range or changing parameters.")
                    else:
                        st.success(f"Backtest Completed for {ticker}!")
                        
                        # Store current run state for Save option
                        st.session_state['last_run'] = {
                            'strategy_name': strategy_choice,
                            'ticker': ticker,
                            'timeframe': timeframe,
                            'total_return': metrics['Total Return (%)'],
                            'sharpe_ratio': metrics['Sharpe Ratio'],
                            'max_drawdown': metrics['Max Drawdown (%)'],
                            'win_rate': metrics['Win Rate (%)'],
                            'total_trades': metrics['Total Trades'],
                            'parameters': params
                        }

                        # Metrics Display Cards
                        col1, col2, col3, col4, col5 = st.columns(5)
                        col1.metric("Strategy Return", f"{metrics['Total Return (%)']}%")
                        col2.metric("Market Return", f"{metrics['Market Return (%)']}%")
                        col3.metric("Sharpe Ratio", metrics['Sharpe Ratio'])
                        col4.metric("Max Drawdown", f"{metrics['Max Drawdown (%)']}%")
                        col5.metric("Win Rate", f"{metrics['Win Rate (%)']}%")

                        col1_val, col2_val = st.columns(2)
                        col1_val.metric("Total Trades Executed", metrics['Total Trades'])
                        col2_val.metric("Final Capital (INR)", metrics['Final Value (₹)'])

                        # Save Capability
                        st.write("---")
                        if st.button("💖 Save this Strategy & Result", type="primary"):
                            save_strategy_to_db(st.session_state['last_run'])
                            st.balloons()
                            st.success("Successfully saved to database!")

                        # Plotly Interactive Chart
                        st.subheader("📈 Performance Visualization")
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                           vertical_spacing=0.08, row_heights=[0.7, 0.3])

                        # Main Price & Buy/Sell signals
                        fig.add_trace(go.Scatter(x=result_df.index, y=result_df['Close'], name='Close Price', line=dict(color='blue')), row=1, col=1)
                        
                        # Add Strategy Specific overlays
                        if strategy_choice == "Moving Average Crossover":
                            fig.add_trace(go.Scatter(x=result_df.index, y=result_df['Fast_MA'], name='Fast MA', line=dict(color='orange', dash='dash')), row=1, col=1)
                            fig.add_trace(go.Scatter(x=result_df.index, y=result_df['Slow_MA'], name='Slow MA', line=dict(color='green', dash='dash')), row=1, col=1)
                        
                        # Plot Buy/Sell Indicators
                        buys = result_df[result_df['Trade_Signal'] == 2]  # Change from Short to Long
                        sells = result_df[result_df['Trade_Signal'] == -2] # Change from Long to Short
                        
                        fig.add_trace(go.Scatter(x=buys.index, y=buys['Close'], mode='markers', marker=dict(symbol='triangle-up', size=12, color='green'), name='Buy Signal'), row=1, col=1)
                        fig.add_trace(go.Scatter(x=sells.index, y=sells['Close'], mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name='Sell Signal'), row=1, col=1)

                        # Portfolio growth
                        fig.add_trace(go.Scatter(x=result_df.index, y=result_df['Portfolio_Value'], name='Portfolio Value', line=dict(color='purple')), row=2, col=1)
                        
                        fig.update_layout(height=600, width=1100, title_text=f"Visual Analysis - {ticker}", xaxis_rangeslider_visible=False)
                        st.plotly_chart(fig, use_container_width=True)

                        # Data Table download option
                        st.subheader("📊 Detailed Trade Logs")
                        st.dataframe(result_df[['Close', 'Position', 'Strategy_Returns', 'Portfolio_Value']].tail(100))

            except Exception as e:
                st.error(f"Error fetching data or parsing strategy: {e}")

with tab2:
    st.header("Saved Strategies Portfolio")
    st.write("Browse and manage the setup configurations and performance profiles you have previously liked and saved.")
    
    saved_data = get_saved_strategies()
    if saved_data.empty:
        st.info("No strategies saved yet. Run a backtest and hit 'Save this Strategy' to log your favorites.")
    else:
        for idx, row in saved_data.iterrows():
            with st.expander(f"✨ {row['strategy_name']} on {row['ticker']} ({row['timestamp']})"):
                cols = st.columns(5)
                cols[0].metric("Total Return", f"{row['total_return']}%")
                cols[1].metric("Sharpe Ratio", row['sharpe_ratio'])
                cols[2].metric("Max Drawdown", f"{row['max_drawdown']}%")
                cols[3].metric("Win Rate", f"{row['win_rate']}%")
                cols[4].metric("Total Trades", int(row['total_trades']))
                
                st.write(f"**Parameters Evaluated:** `{row['parameters']}`")
                st.write(f"**Timeframe Used:** `{row['timeframe']}`")
                
                if st.button("🗑️ Delete Saved Run", key=f"del_{row['id']}"):
                    delete_saved_strategy(row['id'])
                    st.rerun()

with tab3:
    st.markdown("""
    ### 📖 User Guide & Systems Manual
    Welcome to the **Pro-Quant Backtesting Suite** optimized for the Indian Equity Markets (NSE/BSE).
    
    #### How to Search for Assets
    *   **National Stock Exchange (NSE):** Append `.NS` suffix to stock tickers (e.g., `RELIANCE.NS`, `TCS.NS`, `SBIN.NS`).
    *   **Bombay Stock Exchange (BSE):** Append `.BO` suffix to stock tickers (e.g., `500325.BO` or `RELIANCE.BO`).
    *   **Indices:** Use `^NSEI` for Nifty 50 and `^NSEBANK` for Bank Nifty.

    #### Available Strategies
    1.  **Moving Average Crossover:** Classic trend-following. Long position initiated when Fast MA rises above Slow MA; short position initiated when Fast MA crosses below.
    2.  **RSI Mean Reversion:** Momentum-based. Buys when security is oversold (default < 30) and reverses position when overbought (default > 70).
    3.  **MACD Line Crossover:** Measures acceleration. Buys when MACD line crosses above the Signal Line, and sells/shorts on a cross below.

    #### Assumptions
    *   Slippage & Brokerage commissions are assumed at zero.
    *   The backtest is executed using Vectorized Pandas architecture for speedy computation.
    *   Risk-free rate of return is set at `5%` annually (aligned with standard Reserve Bank of India short-term G-Sec rates).
    """)
