# app.py
import streamlit as st
import pandas as pd
import requests  # <--- THIS IS THE MISSING LINE THAT IS NOW ADDED
import csv
import os
from datetime import datetime, timedelta
from config import API_KEY # Your API Key
# Import shared functions from our new core logic file
from core_logic import calculate_indicators_and_score

# --- Page Configuration ---
st.set_page_config(
    page_title="Crypto Analysis Dashboard",
    page_icon="📊",
    layout="wide",
)

# --- Caching ---
# We still cache the main API calls to keep the app fast
@st.cache_data(ttl=900)
def get_api_data(url, params):
    headers = {'accept': 'application/json', 'x-cg-demo-api-key': API_KEY}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

# --- Paper Trading Logic ---
TRADE_FILE = 'paper_trades.csv'
TRADE_AMOUNT_USD = 10.00

def setup_database():
    """Creates the CSV file for trades if it doesn't exist."""
    if not os.path.exists(TRADE_FILE):
        with open(TRADE_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'coin_id', 'name', 'symbol', 'buy_price', 'quantity'])

def log_trade(coin, analysis):
    """Logs a new dummy trade to the CSV file."""
    # Check if we already made a trade for this coin in the last 24 hours
    if os.path.exists(TRADE_FILE):
        try:
            trades_df = pd.read_csv(TRADE_FILE)
            if not trades_df.empty:
                trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
                recent_trades = trades_df[
                    (trades_df['coin_id'] == coin['id']) &
                    (trades_df['timestamp'] > datetime.now() - timedelta(days=1))
                ]
                if not recent_trades.empty:
                    return # Don't log another trade if we already have a recent one
        except pd.errors.EmptyDataError:
            # File is empty, proceed to log trade
            pass

    # Log the new trade
    with open(TRADE_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            coin['id'],
            coin['name'],
            coin['symbol'].upper(),
            analysis['current_price'],
            TRADE_AMOUNT_USD / analysis['current_price']
        ])
    st.toast(f"Logged a ${TRADE_AMOUNT_USD} paper trade for {coin['name']}!", icon="✅")

# --- UI Layout ---
st.title("📈 Advanced Crypto Spot Buying Assistant")
st.markdown("This dashboard analyzes the top 25 coins using an enhanced model and automatically logs paper trades for promising opportunities.")

with st.expander("How the New Scoring Model Works"):
    st.markdown("""
    The "Spot Score" is now calculated from five key areas, each with a specific weight:
    - **Potential (30%):** The ratio of potential upside (to ATH) vs. downside risk (to ATL).
    - **RSI (25%):** A low RSI is a strong indicator of an oversold asset, contributing more to the score.
    - **MACD (20%):** A bullish crossover (MACD line above Signal line) indicates positive momentum.
    - **Bollinger Bands (15%):** A price touching or dipping below the lower Bollinger Band is a powerful buy signal.
    - **Trend (10%):** A price trading above its 50-day moving average confirms a healthy, bullish long-term trend.

    A **"Good to Buy"** signal (Score > 65) will automatically trigger a **$10 paper trade**, which you can track on the **Paper Portfolio** page.
    """)

try:
    setup_database() # Ensure the trade file exists
    top_coins = get_api_data("https://api.coingecko.com/api/v3/coins/markets", {'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 25, 'page': 1})

    st.header("Top 25 Coins Overview")

    all_data = []
    with st.spinner("Analyzing all coins with advanced model..."):
        for coin in top_coins:
            historical_prices_data = get_api_data(f"https://api.coingecko.com/api/v3/coins/{coin['id']}/market_chart", {'vs_currency': 'usd', 'days': '365', 'interval': 'daily'})
            historical_prices = historical_prices_data.get('prices', [])
            
            if not historical_prices:
                continue # Skip coin if no historical data is available

            hist_df = pd.DataFrame(historical_prices, columns=['timestamp', 'price'])
            hist_df['date'] = pd.to_datetime(hist_df['timestamp'], unit='ms')
            hist_df.set_index('date', inplace=True)
            
            analysis = calculate_indicators_and_score(coin, hist_df)
            
            # Auto-trigger paper trade on strong signal
            if analysis['score'] > 65:
                log_trade(coin, analysis)
            
            all_data.append({
                "Rank": coin['market_cap_rank'],
                "Coin": f"{coin['name']} ({coin['symbol'].upper()})",
                "Price": analysis['current_price'],
                "24h %": coin['price_change_percentage_24h'],
                "Spot Score": analysis['score'],
                "RSI": analysis['rsi']
            })

    df = pd.DataFrame(all_data)
    
    # Function to style the dataframe for better visualization
    def style_dataframe(df_to_style):
        def color_24h(val):
            color = 'green' if val > 0 else 'red'
            return f'color: {color}'
        def style_score(score_val):
            if score_val > 65: return "background-color: #2E8B57; color: white;" # SeaGreen
            if score_val < 40: return "background-color: #B22222; color: white;" # FireBrick
            return ""

        return df_to_style.style.format({"Price": "${:,.2f}", "24h %": "{:,.2f}%"})\
            .applymap(color_24h, subset=['24h %'])\
            .applymap(style_score, subset=['Spot Score'])

    st.dataframe(style_dataframe(df), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"An error occurred: {e}. Please check your API key and internet connection.")