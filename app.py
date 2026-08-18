# app.py
"""Indian Market Backtesting App - Streamlit UI"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import INDICES, SECTORS, TIMEFRAMES, INTERVALS_MAX_PERIOD
from data.data_loader import fetch_data
from strategies.strategies import STRATEGY_REGISTRY
from backtest.engine import BacktestEngine
from storage.results_manager import save_result, load_all_results, delete_result

st.set_page_config(page_title="Indian Market Backtester", page_icon="📈", layout="wide")

st.title("📈 Indian Market Backtesting App")
st.caption("Backtest multiple strategies across indices & stocks | NSE/BSE")

# ---------------- SIDEBAR ----------------
st.sidebar.header("⚙️ Backtest Configuration")

# Instrument selection
asset_type = st.sidebar.radio("Asset Type", ["Index", "Stock (by Sector)"])

if asset_type == "Index":
    selected = st.sidebar.multiselect("Select Indices", list(INDICES.keys()),
                                      default=["NIFTY 50"])
    symbols = {name: INDICES[name] for name in selected}
else:
    sector = st.sidebar.selectbox("Select Sector", list(SECTORS.keys()))
    stock_options = SECTORS[sector]
    selected = st.sidebar.multiselect("Select Stocks", stock_options,
                                      default=stock_options[:2])
    symbols = {s.replace(".NS", ""): s for s in selected}

# Timeframe
tf_label = st.sidebar.selectbox("Timeframe", list(TIMEFRAMES.keys()))
interval = TIMEFRAMES[tf_label]
max_period = INTERVALS_MAX_PERIOD.get(interval, "2y")

period = st.sidebar.selectbox(
    "Period",
    ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
    if max_period == "max" else [max_period],
)

# Strategy selection
st.sidebar.subheader("📊 Strategies")
selected_strategies = st.sidebar.multiselect(
    "Choose Strategies", list(STRATEGY_REGISTRY.keys()),
    default=["SMA Crossover"]
)

# Strategy parameters
strategy_params = {}
with st.sidebar.expander("🔧 Strategy Parameters"):
    for strat in selected_strategies:
        st.markdown(f"**{strat}**")
        params = {}
        if "SMA" in strat or "EMA" in strat:
            params["fast"] = st.number_input(f"{strat} Fast", 5, 100, 20, key=f"{strat}_f")
            params["slow"] = st.number_input(f"{strat} Slow", 10, 200, 50, key=f"{strat}_s")
        if "RSI" in strat:
            params["period"] = st.number_input(f"{strat} RSI Period", 5, 50, 14, key=f"{strat}_p")
        if strat == "RSI Oversold/Overbought":
            params["oversold"] = st.number_input("Oversold", 10, 40, 30, key=f"{strat}_os")
            params["overbought"] = st.number_input("Overbought", 60, 90, 70, key=f"{strat}_ob")
        strategy_params[strat] = params

# Capital & risk
st.sidebar.subheader("💰 Capital & Risk")
capital = st.sidebar.number_input("Initial Capital (₹)", 10000, 10000000, 100000, step=10000)
pos_size = st.sidebar.slider("Position Size (%)", 10, 100, 100) / 100
use_sl = st.sidebar.checkbox("Use Stop Loss")
sl = st.sidebar.slider("Stop Loss %", 1, 20, 5) / 100 if use_sl else None
use_tp = st.sidebar.checkbox("Use Take Profit")
tp = st.sidebar.slider("Take Profit %", 1, 50, 10) / 100 if use_tp else None

run_bt = st.sidebar.button("🚀 Run Backtest", type="primary", use_container_width=True)

# ---------------- MAIN TABS ----------------
tab1, tab2 = st.tabs(["🧪 Backtest", "⭐ Saved Results"])

with tab1:
    if run_bt:
        if not symbols or not selected_strategies:
            st.warning("Please select at least one instrument and one strategy.")
        else:
            all_results = []
            progress = st.progress(0)
            total = len(symbols) * len(selected_strategies)
            count = 0

            for sym_name, sym in symbols.items():
                df = fetch_data(sym, interval=interval, period=period)
                if df is None or len(df) < 50:
                    st.warning(f"⚠️ Not enough data for {sym_name}")
                    continue

                for strat_name in selected_strategies:
                    StrategyClass = STRATEGY_REGISTRY[strat_name]
                    strategy = StrategyClass(strategy_params.get(strat_name, {}))
                    signal_df = strategy.generate_signals(df.copy())

                    engine = BacktestEngine(
                        initial_capital=capital, position_size=pos_size,
                        stop_loss=sl, take_profit=tp,
                    )
                    result = engine.run(signal_df)
                    metrics = result["metrics"]
                    metrics["Instrument"] = sym_name
                    metrics["Strategy"] = strat_name
                    all_results.append({
                        "meta": metrics, "result": result,
                        "signal_df": signal_df,
                        "config": {
                            "symbol": sym, "instrument": sym_name,
                            "strategy": strat_name, "timeframe": tf_label,
                            "period": period, "capital": capital,
                            "params": strategy_params.get(strat_name, {}),
                        }
                    })
                    count += 1
                    progress.progress(count / total)

            progress.empty()
            st.session_state["results"] = all_results

    # Display results
    if "results" in st.session_state and st.session_state["results"]:
        results = st.session_state["results"]

        # ---- Summary table ----
        st.subheader("📋 Results Summary")
        summary = pd.DataFrame([r["meta"] for r in results])
        cols = ["Instrument", "Strategy", "Total Return %", "Win Rate %",
                "Max Drawdown %", "Sharpe Ratio", "Total Trades", "Profit Factor"]
        summary = summary[[c for c in cols if c in summary.columns]]

        def color_returns(val):
            if isinstance(val, (int, float)):
                return "color: green" if val > 0 else "color: red"
            return ""

        st.dataframe(
            summary.style.map(color_returns, subset=["Total Return %"]),
            use_container_width=True, height=250,
        )

        # Best strategy highlight
        best = summary.loc[summary["Total Return %"].idxmax()]
        st.success(f"🏆 Best: **{best['Strategy']}** on **{best['Instrument']}** "
                   f"→ {best['Total Return %']}% return")

        # ---- Detailed view ----
        st.subheader("🔍 Detailed Analysis")
        labels = [f"{r['meta']['Instrument']} - {r['meta']['Strategy']}" for r in results]
        choice = st.selectbox("Select a result to inspect", range(len(labels)),
                              format_func=lambda i: labels[i])
        selected_r = results[choice]

        # Metrics cards
        m = selected_r["meta"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Return", f"{m['Total Return %']}%")
        c2.metric("Win Rate", f"{m['Win Rate %']}%")
        c3.metric("Max Drawdown", f"{m['Max Drawdown %']}%")
        c4.metric("Sharpe Ratio", m["Sharpe Ratio"])
        c1.metric("Total Trades", m["Total Trades"])
        c2.metric("Profit Factor", m["Profit Factor"])
        c3.metric("Avg Win", f"{m['Avg Win %']}%")
        c4.metric("Final Equity", f"₹{m['Final Equity']:,.0f}")

        # ---- Charts ----
        sig_df = selected_r["signal_df"]
        equity = selected_r["result"]["equity"]

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.6, 0.4],
                            subplot_titles=("Price & Signals", "Equity Curve"))

        fig.add_trace(go.Candlestick(
            x=sig_df.index, open=sig_df["Open"], high=sig_df["High"],
            low=sig_df["Low"], close=sig_df["Close"], name="Price"), row=1, col=1)

        buys = sig_df[sig_df["Signal"] == 1]
        sells = sig_df[sig_df["Signal"] == -1]
        fig.add_trace(go.Scatter(x=buys.index, y=buys["Close"], mode="markers",
                                 marker=dict(symbol="triangle-up", size=12, color="green"),
                                 name="Buy"), row=1, col=1)
        fig.add_trace(go.Scatter(x=sells.index, y=sells["Close"], mode="markers",
                                 marker=dict(symbol="triangle-down", size=12, color="red"),
                                 name="Sell"), row=1, col=1)

        fig.add_trace(go.Scatter(x=equity.index, y=equity["Equity"],
                                 fill="tozeroy", name="Equity",
                                 line=dict(color="blue")), row=2, col=1)

        fig.update_layout(height=700, xaxis_rangeslider_visible=False,
                          showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        # ---- Trades table ----
        trades = selected_r["result"]["trades"]
        if not trades.empty:
            with st.expander(f"📜 Trade Log ({len(trades)} trades)"):
                st.dataframe(trades, use_container_width=True)
                csv = trades.to_csv(index=False).encode()
                st.download_button("⬇️ Download Trades CSV", csv,
                                   "trades.csv", "text/csv")

        # ---- Save result ----
        st.subheader("⭐ Save This Result")
        col_a, col_b = st.columns([3, 1])
        save_name = col_a.text_input("Name your favorite strategy result",
                                     value=f"{m['Strategy']}_{m['Instrument']}")
        if col_b.button("💾 Save", use_container_width=True):
            path = save_result(save_name, selected_r["config"], m)
            st.success(f"Saved! ({path})")
    else:
        st.info("👈 Configure your backtest in the sidebar and click **Run Backtest**")

with tab2:
    st.subheader("⭐ Your Saved Strategy Results")
    saved = load_all_results()
    if not saved:
        st.info("No saved results yet. Run a backtest and save your favorites!")
    else:
        for r in saved:
            with st.expander(f"📌 {r['name']}  —  saved {r['saved_at']}"):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.json(r["config"])
                    st.markdown("**Metrics:**")
                    st.dataframe(pd.DataFrame([r["metrics"]]),
                                 use_container_width=True)
                with col2:
                    if st.button("🗑️ Delete", key=r["_file"]):
                        delete_result(r["_file"])
                        st.rerun()
