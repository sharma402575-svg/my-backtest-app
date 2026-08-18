import streamlit as st

st.set_page_config(page_title="Backtesting App", layout="wide")

st.title("📈 Web-Based Backtesting Application")
st.write("Welcome! This is the foundation of your strategy backtester.")

ticker = st.text_input("Enter Stock / Ticker Symbol", value="AAPL")
st.write(f"Selected Ticker: **{ticker}**")
