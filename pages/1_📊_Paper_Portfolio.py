# pages/1_📊_Paper_Portfolio.py
import streamlit as st
import pandas as pd
import os
import requests
from config import API_KEY

TRADE_FILE = 'paper_trades.csv'

st.set_page_config(page_title="Paper Trading Portfolio", page_icon="💰", layout="wide")

st.title("💰 Paper Trading Portfolio")
st.markdown("This page tracks the performance of the automated dummy trades triggered by the dashboard's analysis.")

if not os.path.exists(TRADE_FILE) or pd.read_csv(TRADE_FILE).empty:
    st.info("No paper trades have been logged yet. A $10 trade is automatically placed when a coin's score exceeds 65 on the main dashboard.")
else:
    trades_df = pd.read_csv(TRADE_FILE)
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    
    # --- Get Current Prices to Calculate P/L ---
    portfolio_coin_ids = trades_df['coin_id'].unique().tolist()
    
    if not portfolio_coin_ids:
        st.info("No active trades found.")
    else:
        ids_string = ",".join(portfolio_coin_ids)
        params = {'vs_currency': 'usd', 'ids': ids_string}
        headers = {'accept': 'application/json', 'x-cg-demo-api-key': API_KEY}
        
        try:
            response = requests.get("https://api.coingecko.com/api/v3/simple/price", params=params, headers=headers)
            response.raise_for_status()
            current_prices = response.json()

            # --- Calculate P/L for each trade ---
            trades_df['current_price'] = trades_df['coin_id'].apply(lambda x: current_prices.get(x, {}).get('usd', 0))
            trades_df['initial_value'] = trades_df['buy_price'] * trades_df['quantity']
            trades_df['current_value'] = trades_df['current_price'] * trades_df['quantity']
            trades_df['pnl'] = trades_df['current_value'] - trades_df['initial_value']
            trades_df['pnl_percent'] = (trades_df['pnl'] / trades_df['initial_value']) * 100

            # --- Display Summary Metrics ---
            total_invested = trades_df['initial_value'].sum()
            total_current_value = trades_df['current_value'].sum()
            total_pnl = trades_df['pnl'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Invested", f"${total_invested:,.2f}")
            col2.metric("Portfolio's Current Value", f"${total_current_value:,.2f}")
            col3.metric("Total Profit / Loss", f"${total_pnl:,.2f}", delta=f"{total_pnl / total_invested:.2%}" if total_invested > 0 else "0.00%")

            # --- Display Trade Details Table ---
            st.subheader("All Trades")

            def style_pnl(val):
                color = 'green' if val > 0 else 'red' if val < 0 else 'grey'
                return f'color: {color}'

            display_df = trades_df[['timestamp', 'name', 'buy_price', 'current_price', 'current_value', 'pnl', 'pnl_percent']].copy()
            display_df.sort_values('timestamp', ascending=False, inplace=True)

            st.dataframe(display_df.style.format({
                'buy_price': "${:,.4f}",
                'current_price': "${:,.4f}",
                'current_value': "${:,.2f}",
                'pnl': "${:,.2f}",
                'pnl_percent': "{:,.2f}%"
            }).applymap(style_pnl, subset=['pnl', 'pnl_percent']),
            use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Could not fetch current prices for the portfolio: {e}")