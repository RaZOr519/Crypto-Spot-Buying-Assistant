# pages/1_📊_Paper_Portfolio.py
import streamlit as st
import pandas as pd
import os
# Import all necessary functions from the core logic file
from core_logic import (
    get_top_coins_data,
    get_api_data,
    log_trade,
    calculate_indicators_and_score # We need this to get the current price for a manual trade
)

TRADE_FILE = 'paper_trades.csv'

st.set_page_config(page_title="Paper Trading Portfolio", page_icon="💰", layout="wide")
st.title("💰 Paper Trading Portfolio")
st.markdown("This page tracks the performance of both automated and manually logged dummy trades.")

# --- Manual Trade Logger ---
with st.expander("Log a Manual Trade"):
    try:
        top_coins = get_top_coins_data()
        coin_names = [coin['name'] for coin in top_coins]
        
        selected_coin_name = st.selectbox("Select a coin to trade:", options=coin_names)
        
        if st.button("Log $10 Manual Purchase"):
            selected_coin_data = next((c for c in top_coins if c['name'] == selected_coin_name), None)
            if selected_coin_data:
                manual_analysis = {'current_price': selected_coin_data['current_price']}
                log_trade(selected_coin_data, manual_analysis, trade_type='manual')
                st.success(f"Successfully logged manual trade for {selected_coin_name}.")
                # Clear cache to force a re-read of the trade file immediately
                st.cache_data.clear()
    except Exception as e:
        st.error(f"Could not load coins for manual trading. Error: {e}")

# --- Portfolio Display ---
if not os.path.exists(TRADE_FILE) or pd.read_csv(TRADE_FILE).empty:
    st.info("No paper trades have been logged yet. A $10 trade is automatically placed when a coin's score exceeds 65 on the main dashboard, or you can add one manually above.")
else:
    trades_df = pd.read_csv(TRADE_FILE)
    
    # --- ROBUST DATE CONVERSION (THE FIX) ---
    # 1. Use errors='coerce' to turn any bad dates into NaT (Not a Time) instead of crashing.
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'], errors='coerce')
    # 2. Drop any rows where the date conversion failed.
    trades_df.dropna(subset=['timestamp'], inplace=True)
    
    portfolio_coin_ids = trades_df['coin_id'].unique().tolist()
    
    if not portfolio_coin_ids:
        st.info("No valid trades found to display.")
    else:
        try:
            ids_string = ",".join(map(str, portfolio_coin_ids))
            current_prices = get_api_data("https://api.coingecko.com/api/v3/simple/price", {'vs_currency': 'usd', 'ids': ids_string})

            trades_df['current_price'] = trades_df['coin_id'].apply(lambda x: current_prices.get(str(x), {}).get('usd', 0))
            trades_df['current_value'] = trades_df['current_price'] * trades_df['quantity']
            trades_df['pnl'] = trades_df['current_value'] - (trades_df['buy_price'] * trades_df['quantity'])
            trades_df['pnl_percent'] = (trades_df['pnl'] / (trades_df['buy_price'] * trades_df['quantity'])) * 100

            total_invested = (trades_df['buy_price'] * trades_df['quantity']).sum()
            total_current_value = trades_df['current_value'].sum()
            total_pnl = trades_df['pnl'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Invested", f"${total_invested:,.2f}")
            col2.metric("Portfolio's Current Value", f"${total_current_value:,.2f}")
            col3.metric("Total Profit / Loss", f"${total_pnl:,.2f}", delta=f"{total_pnl / total_invested:.2%}" if total_invested > 0 else "0.00%")

            st.subheader("All Trades")

            def style_pnl(val): return f'color: {"green" if val > 0 else "red" if val < 0 else "grey"}'
            def style_type(val):
                color = "#3498db" if val == 'manual' else "#2ecc71"
                return f'background-color: {color}; color: white; border-radius: 5px; padding: 2px 6px; text-align: center;'
            
            display_df = trades_df[['timestamp', 'name', 'trade_type', 'buy_price', 'current_price', 'current_value', 'pnl', 'pnl_percent']].copy()
            display_df.sort_values('timestamp', ascending=False, inplace=True)

            st.dataframe(display_df.style.format({
                'buy_price': "${:,.4f}", 'current_price': "${:,.4f}", 'current_value': "${:,.2f}",
                'pnl': "${:,.2f}", 'pnl_percent': "{:,.2f}%"
            }).applymap(style_pnl, subset=['pnl', 'pnl_percent'])\
              .applymap(style_type, subset=['trade_type']),
            use_container_width=True, hide_index=True)
            
        except Exception as e:
            st.error(f"Could not process portfolio data. Error: {e}")