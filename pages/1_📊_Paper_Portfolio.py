# pages/1_📊_Paper_Portfolio.py
import streamlit as st
import pandas as pd
import os
import requests # Import requests to catch specific HTTP errors
from datetime import datetime
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

if 'portfolio_df' not in st.session_state:
    st.session_state.portfolio_df = load_portfolio_data()

# --- Manual Trade Logger ---
with st.expander("Log a Manual Trade", expanded=True):
    # (This section is unchanged and correct)
    try:
        top_coins = get_top_coins_data()
        coin_names = [coin['name'] for coin in top_coins]
        selected_coin_name = st.selectbox("Select a coin to trade:", options=coin_names, key="manual_coin_select")
        if st.button(f"Log ${TRADE_AMOUNT_USD:.2f} Manual Purchase"):
            selected_coin_data = next((c for c in top_coins if c['name'] == selected_coin_name), None)
            if selected_coin_data:
                analysis_for_trade = {'current_price': selected_coin_data['current_price']}
                log_trade(selected_coin_data, analysis_for_trade, trade_type='manual')
                new_trade_data = {'timestamp': pd.to_datetime(datetime.now().isoformat()),'coin_id': selected_coin_data['id'],'name': selected_coin_data['name'],'symbol': selected_coin_data['symbol'].upper(),'buy_price': analysis_for_trade['current_price'],'quantity': TRADE_AMOUNT_USD / analysis_for_trade['current_price'],'trade_type': 'manual'}
                new_trade_df = pd.DataFrame([new_trade_data])
                st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, new_trade_df], ignore_index=True)
                st.rerun()
    except Exception as e:
        st.error(f"Could not load coins for manual trading. Error: {e}")

# --- Portfolio Display ---
trades_df = st.session_state.portfolio_df

if trades_df.empty:
    st.info("No paper trades have been logged yet.")
else:
    # --- AGGRESSIVE ID CLEANING & DEBUGGING (THE FIX) ---
    st.markdown("---") # Visual separator
    st.subheader("Data Integrity Check")
    
    # 1. Drop rows with missing coin_id right away
    cleaned_trades_df = trades_df.dropna(subset=['coin_id'])
    
    # 2. Get unique IDs and aggressively sanitize them
    unique_ids = cleaned_trades_df['coin_id'].unique()
    sanitized_ids = []
    for id_val in unique_ids:
        if pd.isna(id_val): continue # Skip if NaN
        id_str = str(id_val).strip() # Convert to string and strip whitespace
        if id_str.endswith('.0'): id_str = id_str[:-2] # Handle float strings like '825.0'
        if id_str: sanitized_ids.append(id_str) # Add to list if not empty

    # 3. Display debugging info directly in the UI
    with st.expander("Click to see API Request Details (for debugging)"):
        st.write("The following list of IDs was generated from your `paper_trades.csv` file to fetch current prices.")
        st.code(f"Cleaned IDs List: {sanitized_ids}")
        ids_string = ",".join(sanitized_ids)
        st.code(f"Final 'ids' parameter sent to API: {ids_string}")

    # 4. Only proceed if we have valid IDs to query
    if not sanitized_ids:
        st.warning("No valid trades with recognized coin IDs found in the portfolio.")
    else:
        with st.spinner("Fetching latest prices to update portfolio..."):
            try:
                current_prices = get_api_data("https://api.coingecko.com/api/v3/simple/price", {'vs_currency': 'usd', 'ids': ids_string})

                # --- The rest of the logic remains the same ---
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
                        'Invested': "${:,.2f}", 'current_value': "${:,.2f}", 'pnl': "${:,.2f}"
                    }).applymap(style_pnl, subset=['pnl']).applymap(style_type, subset=['trade_type']),
                    use_container_width=True, hide_index=True
                )
            
            # --- Better Error Handling ---
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 422:
                    st.error("API Error (422 - Unprocessable Entity): CoinGecko rejected the list of coin IDs.")
                    st.error("This means one of the IDs in the 'API Request Details' debug box above is invalid. Please check your paper_trades.csv file for corrupted entries.")
                else:
                    st.error(f"An HTTP error occurred while fetching prices: {e}")
            except Exception as e:
                st.error(f"A general error occurred while processing the portfolio: {e}")