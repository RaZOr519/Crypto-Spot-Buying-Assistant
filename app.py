# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
# Import all necessary functions from our new core logic file
from core_logic import (
    get_top_coins_data,
    get_api_data,
    calculate_indicators_and_score,
    setup_database,
    log_trade
)

# --- Page Configuration and Session State ---
st.set_page_config(page_title="Crypto Analysis Dashboard", page_icon="📊", layout="wide")

# Initialize session state for start time, runs only once per session
if 'app_start_time' not in st.session_state:
    st.session_state.app_start_time = datetime.now()

# --- Helper function for uptime formatting ---
def format_timedelta(td):
    """Formats a timedelta object into a human-readable string."""
    days = td.days
    hours, rem = divmod(td.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m"

# --- UI Layout ---
st.title("📈 Advanced Crypto Spot Buying Assistant")
st.markdown("This dashboard analyzes the top 25 coins using an enhanced model and automatically logs paper trades for promising opportunities.")

with st.expander("How the New Scoring Model Works"):
    st.markdown("""
    The "Spot Score" is now calculated from five key areas. A **"Good to Buy"** signal (Score > 65) will automatically trigger a **$10 paper trade**, which you can track on the **Paper Portfolio** page.
    """)

try:
    setup_database()  # Ensure the trade file exists with the new column
    top_coins = get_top_coins_data()
    st.header("Top 25 Coins Overview")

    all_data = []
    with st.spinner("Analyzing all coins with advanced model..."):
        for coin in top_coins:
            historical_prices_data = get_api_data(f"https://api.coingecko.com/api/v3/coins/{coin['id']}/market_chart", {'vs_currency': 'usd', 'days': '365', 'interval': 'daily'})
            historical_prices = historical_prices_data.get('prices', [])
            
            if not historical_prices: continue

            hist_df = pd.DataFrame(historical_prices, columns=['timestamp', 'price'])
            hist_df.set_index(pd.to_datetime(hist_df['timestamp'], unit='ms'), inplace=True)
            
            analysis = calculate_indicators_and_score(coin, hist_df)
            
            if analysis['score'] > 65:
                # Log trade with type 'auto'
                log_trade(coin, analysis, trade_type='auto')
            
            all_data.append({
                "Rank": coin['market_cap_rank'], "Coin": f"{coin['name']} ({coin['symbol'].upper()})",
                "Price": analysis['current_price'], "24h %": coin['price_change_percentage_24h'],
                "Spot Score": analysis['score'], "RSI": analysis['rsi']
            })

    df = pd.DataFrame(all_data)
    
    def style_dataframe(df_to_style):
        def color_24h(val): return f'color: {"green" if val > 0 else "red"}'
        def style_score(s): return f'background-color: {"#2E8B57" if s > 65 else "#B22222" if s < 40 else ""}; color: white;' if s > 65 or s < 40 else ""
        return df_to_style.style.format({"Price": "${:,.2f}", "24h %": "{:,.2f}%"}).applymap(color_24h, subset=['24h %']).applymap(style_score, subset=['Spot Score'])

    st.dataframe(style_dataframe(df), use_container_width=True, hide_index=True)

    # --- NEW: App Stats Footer ---
    st.divider()
    uptime = datetime.now() - st.session_state.app_start_time
    st.markdown(f"""
        <div style="text-align: center; color: grey;">
            Session Started: {st.session_state.app_start_time.strftime('%Y-%m-%d %H:%M:%S')} | 
            Running for: {format_timedelta(uptime)}
        </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"An error occurred: {e}. Please check your API key and internet connection.")