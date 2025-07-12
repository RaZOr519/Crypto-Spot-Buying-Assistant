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

# Initialize session state for start time and last API call time
if 'app_start_time' not in st.session_state:
    st.session_state.app_start_time = datetime.now()
if 'last_api_call' not in st.session_state:
    st.session_state.last_api_call = "N/A" # Default value

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

with st.expander("How the Scoring & Data Refresh Works"):
    st.markdown("""
    The **Spot Score** is calculated from five key areas. A score > 65 triggers an automated **$10 paper trade**.
    - **Data Caching:** To ensure fast performance and respect API limits, all market data is cached. A fresh API call is only made if the stored data is **older than 15 minutes**. The 'Last API Call' time below indicates when the data was last fetched from the source.
    """)

try:
    setup_database()  # Ensure the trade file exists

    # We will wrap the main API call to update the timestamp
    with st.spinner("Fetching latest market data..."):
        # This function call is cached. The code inside only runs if cache is expired.
        top_coins = get_top_coins_data()
        # We record the time right after the call. If it came from cache, the time won't update.
        # A more robust way is to check the cache info, but this is simpler and effective.
        # Let's refine this to be more accurate by checking the cached function's info.
        if get_top_coins_data.get_stats().cache_misses > 0:
             st.session_state.last_api_call = datetime.now()

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

    # --- App Stats Footer ---
    st.divider()
    uptime = datetime.now() - st.session_state.app_start_time
    last_call_str = st.session_state.last_api_call.strftime('%Y-%m-%d %H:%M:%S') if isinstance(st.session_state.last_api_call, datetime) else st.session_state.last_api_call
    
    st.markdown(f"""
        <div style="text-align: center; color: grey;">
            Session Started: {st.session_state.app_start_time.strftime('%Y-%m-%d %H:%M:%S')} | 
            Running for: {format_timedelta(uptime)} |
            Last API Call: {last_call_str} (refreshes every 15 mins)
        </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"An error occurred: {e}. Please check your API key and internet connection.")