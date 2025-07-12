# pages/1_📊_Paper_Portfolio.py
import streamlit as st
import pandas as pd
import os
# Import all necessary functions from the core logic file
from core_logic import (
    get_top_coins_data,
    get_api_data,
    log_trade,
    TRADE_FILE,
    TRADE_AMOUNT_USD
)

st.set_page_config(page_title="Paper Trading Portfolio", page_icon="💰", layout="wide")
st.title("💰 Paper Trading Portfolio")
st.markdown("This page tracks the performance of both automated and manually logged dummy trades.")

# --- NEW: A dedicated, cached function to load and process portfolio data ---
# This helps keep our code clean and avoids re-reading the file unnecessarily.
@st.cache_data(ttl=30) # A short cache to avoid re-reading the file on minor UI interactions
def load_portfolio_data():
    """Loads, cleans, and returns the portfolio DataFrame from the CSV file."""
    if not os.path.exists(TRADE_FILE) or pd.read_csv(TRADE_FILE).empty:
        return pd.DataFrame() # Return an empty DataFrame if no file or trades exist

    trades_df = pd.read_csv(TRADE_FILE)
    # Robust date conversion
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'], errors='coerce')
    trades_df.dropna(subset=['timestamp'], inplace=True)
    return trades_df

# --- Manual Trade Logger ---
with st.expander("Log a Manual Trade"):
    try:
        top_coins = get_top_coins_data()
        coin_names = [coin['name'] for coin in top_coins]
        
        selected_coin_name = st.selectbox("Select a coin to trade:", options=coin_names)
        
        if st.button(f"Log ${TRADE_AMOUNT_USD:.2f} Manual Purchase"):
            selected_coin_data = next((c for c in top_coins if c['name'] == selected_coin_name), None)
            if selected_coin_data:
                manual_analysis = {'current_price': selected_coin_data['current_price']}
                log_trade(selected_coin_data, manual_analysis, trade_type='manual')
                
                # --- KEY CHANGE: Force an immediate re-run of the script ---
                # This makes the new trade appear instantly in the portfolio below.
                st.rerun()

    except Exception as e:
        st.error(f"Could not load coins for manual trading. Error: {e}")

# --- Portfolio Display ---
trades_df = load_portfolio_data()

if trades_df.empty:
    st.info("No paper trades have been logged yet. A $10 trade is automatically placed when a coin's score exceeds 65 on the main dashboard, or you can add one manually above.")
else:
    portfolio_coin_ids = trades_df['coin_id'].unique().tolist()
    
    with st.spinner("Fetching latest prices to update portfolio..."):
        try:
            ids_string = ",".join(map(str, portfolio_coin_ids))
            current_prices = get_api_data("https://api.coingecko.com/api/v3/simple/price", {'vs_currency': 'usd', 'ids': ids_string})

            # --- ENHANCED P/L CALCULATION ---
            trades_df['current_price'] = trades_df['coin_id'].apply(lambda x: current_prices.get(str(x), {}).get('usd', 0))
            trades_df['initial_value'] = TRADE_AMOUNT_USD # Every trade is a fixed $10
            trades_df['current_value'] = trades_df['current_price'] * trades_df['quantity']
            trades_df['pnl'] = trades_df['current_value'] - trades_df['initial_value']
            trades_df['pnl_percent'] = (trades_df['pnl'] / trades_df['initial_value']) * 100

            # --- Summary Metrics ---
            total_invested = trades_df['initial_value'].sum()
            total_current_value = trades_df['current_value'].sum()
            total_pnl = trades_df['pnl'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Invested", f"${total_invested:,.2f}")
            col2.metric("Portfolio's Current Value", f"${total_current_value:,.2f}")
            col3.metric("Total Profit / Loss", f"${total_pnl:,.2f}", delta=f"{total_pnl / total_invested:.2%}" if total_invested > 0 else "0.00%")

            # --- ENHANCED Display Table ---
            st.subheader("All Trades")

            def style_pnl(val): return f'color: {"#2E8B57" if val > 0 else "#B22222" if val < 0 else "grey"}' # Green/Red
            def style_type(val):
                color = "#3498db" if val == 'manual' else "#2ecc71" # Blue for manual, Green for auto
                return f'background-color: {color}; color: white; border-radius: 5px; padding: 2px 6px; text-align: center;'
            
            # --- We now explicitly show Initial and Current Value for clarity ---
            display_df = trades_df[[
                'timestamp', 'name', 'trade_type', 'buy_price', 
                'current_price', 'initial_value', 'current_value', 'pnl'
            ]].copy()
            display_df.rename(columns={'initial_value': 'Invested'}, inplace=True)
            display_df.sort_values('timestamp', ascending=False, inplace=True)

            st.dataframe(
                display_df.style.format({
                    'buy_price': "${:,.4f}", 'current_price': "${:,.4f}",
                    'Invested': "${:,.2f}", 'current_value': "${:,.2f}",
                    'pnl': "${:,.2f}"
                }).applymap(style_pnl, subset=['pnl'])\
                  .applymap(style_type, subset=['trade_type']),
                use_container_width=True, 
                hide_index=True
            )
            
        except Exception as e:
            st.error(f"Could not process portfolio data. Error: {e}")