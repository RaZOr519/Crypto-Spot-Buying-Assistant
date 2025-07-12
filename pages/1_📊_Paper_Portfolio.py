# pages/1_📊_Paper_Portfolio.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime
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

def load_portfolio_data():
    """Loads, cleans, and returns the portfolio DataFrame from the CSV file."""
    if not os.path.exists(TRADE_FILE) or pd.read_csv(TRADE_FILE).empty:
        return pd.DataFrame(columns=['timestamp', 'coin_id', 'name', 'symbol', 'buy_price', 'quantity', 'trade_type'])

    trades_df = pd.read_csv(TRADE_FILE)
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'], format="ISO8601", errors='coerce')
    trades_df.dropna(subset=['timestamp'], inplace=True)
    return trades_df

# Initialize the portfolio in the session state on the first run
if 'portfolio_df' not in st.session_state:
    st.session_state.portfolio_df = load_portfolio_data()


# --- Manual Trade Logger ---
with st.expander("Log a Manual Trade", expanded=True):
    try:
        top_coins = get_top_coins_data()
        coin_names = [coin['name'] for coin in top_coins]
        
        selected_coin_name = st.selectbox("Select a coin to trade:", options=coin_names, key="manual_coin_select")
        
        if st.button(f"Log ${TRADE_AMOUNT_USD:.2f} Manual Purchase"):
            selected_coin_data = next((c for c in top_coins if c['name'] == selected_coin_name), None)
            if selected_coin_data:
                # 1. Log the trade to the CSV file for persistence
                analysis_for_trade = {'current_price': selected_coin_data['current_price']}
                log_trade(selected_coin_data, analysis_for_trade, trade_type='manual')
                
                # --- THE GUARANTEED FIX: Update the session state DataFrame directly in-memory ---
                
                # 2. Create a new DataFrame for the single new trade
                new_trade_data = {
                    'timestamp': pd.to_datetime(datetime.now().isoformat()),
                    'coin_id': selected_coin_data['id'],
                    'name': selected_coin_data['name'],
                    'symbol': selected_coin_data['symbol'].upper(),
                    'buy_price': analysis_for_trade['current_price'],
                    'quantity': TRADE_AMOUNT_USD / analysis_for_trade['current_price'],
                    'trade_type': 'manual'
                }
                new_trade_df = pd.DataFrame([new_trade_data])
                
                # 3. Concatenate the new trade DataFrame with the existing one in session state
                st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, new_trade_df], ignore_index=True)
                
                # 4. Rerun to instantly reflect the change from the updated session state
                st.rerun()

    except Exception as e:
        st.error(f"Could not load coins for manual trading. Error: {e}")

# --- Portfolio Display ---
# The app now reads directly from session state, which we manually keep updated.
trades_df = st.session_state.portfolio_df

if trades_df.empty:
    st.info("No paper trades have been logged yet. A $10 trade is automatically placed when a coin's score exceeds 65 on the main dashboard, or you can add one manually above.")
else:
    portfolio_coin_ids = trades_df['coin_id'].unique().tolist()
    
    with st.spinner("Fetching latest prices to update portfolio..."):
        try:
            ids_string = ",".join(map(str, portfolio_coin_ids))
            current_prices = get_api_data("https://api.coingecko.com/api/v3/simple/price", {'vs_currency': 'usd', 'ids': ids_string})

            trades_df['current_price'] = trades_df['coin_id'].apply(lambda x: current_prices.get(str(x), {}).get('usd', 0))
            trades_df['initial_value'] = TRADE_AMOUNT_USD
            trades_df['current_value'] = trades_df['current_price'] * trades_df['quantity']
            trades_df['pnl'] = trades_df['current_value'] - trades_df['initial_value']
            trades_df['pnl_percent'] = (trades_df['pnl'] / trades_df['initial_value']).replace([float('inf'), -float('inf')], 0) * 100

            total_invested = trades_df['initial_value'].sum()
            total_current_value = trades_df['current_value'].sum()
            total_pnl = trades_df['pnl'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Invested", f"${total_invested:,.2f}")
            col2.metric("Portfolio's Current Value", f"${total_current_value:,.2f}")
            col3.metric("Total Profit / Loss", f"${total_pnl:,.2f}", delta=f"{total_pnl / total_invested:.2%}" if total_invested > 0 else "0.00%")

            st.subheader("All Trades")

            def style_pnl(val): return f'color: {"#2E8B57" if val > 0 else "#B22222" if val < 0 else "grey"}'
            def style_type(val):
                color = "#3498db" if val == 'manual' else "#2ecc71"
                return f'background-color: {color}; color: white; border-radius: 5px; padding: 2px 6px; text-align: center;'
            
            display_df = trades_df[['timestamp', 'name', 'trade_type', 'buy_price', 'current_price', 'initial_value', 'current_value', 'pnl']].copy()
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